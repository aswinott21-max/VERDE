
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from orders.models import Order, OrderStatusHistory
from referrals.models import Referral, ReferralOffer, ReferralReward
from referrals.services import (
    credit_referral_reward,
    process_referral,
    review_credited_referral_for_exceptions,
)
from referrals.tasks import process_pending_referrals
from wallet.models import Wallet, WalletTransaction


User = get_user_model()


class ReferralProcessingTests(TestCase):
    def setUp(self):
        self.referrer = User.objects.create_user(
            email="referrer@example.com",
            password="test-password",
            full_name="Test Referrer",
            phone="9000000001",
        )
        self.referred_user = User.objects.create_user(
            email="referred@example.com",
            password="test-password",
            full_name="Test Referred User",
            phone="9000000002",
        )

        self.offer = ReferralOffer.objects.create(
            reward_amount=Decimal("100.00"),
            is_active=True,
        )

        self.referral = Referral.objects.create(
            referrer=self.referrer,
            referred_user=self.referred_user,
            referral_code="TESTCODE",
            referral_offer=self.offer,
            reward_amount=Decimal("100.00"),
        )

    def create_delivered_order(
        self,
        add_delivery_history=True,
        *,
        user=None,
        order_number="TEST-ORDER-001",
        status="DELIVERED",
    ):
        order = Order.objects.create(
            user=user or self.referred_user,
            order_number=order_number,
            delivery_method="STANDARD",
            payment_method="COD",
            payment_status="PAID",
            status=status,
        )

        if add_delivery_history and status == "DELIVERED":
            history = OrderStatusHistory.objects.create(
                order=order,
                status="DELIVERED",
            )
            OrderStatusHistory.objects.filter(pk=history.pk).update(
                created_at=timezone.now() - timedelta(days=5)
            )

        return order

    def create_referral_for(self, referred_user, referral_code):
        return Referral.objects.create(
            referrer=self.referrer,
            referred_user=referred_user,
            referral_code=referral_code,
            referral_offer=self.offer,
            reward_amount=self.offer.reward_amount,
        )

    def test_no_paid_order_stays_pending(self):
        referral, rewards = process_referral(self.referral.pk)

        self.assertEqual(referral.status, Referral.Status.PENDING)
        self.assertEqual(rewards, [])

    def test_missing_delivery_history_requires_review(self):
        self.create_delivered_order(add_delivery_history=False)

        referral, rewards = process_referral(self.referral.pk)

        self.assertEqual(referral.status, Referral.Status.MANUAL_REVIEW)
        self.assertEqual(rewards, [])

    def test_eligible_referral_creates_two_pending_rewards(self):
        self.create_delivered_order()

        referral, rewards = process_referral(self.referral.pk)

        self.assertEqual(referral.status, Referral.Status.ELIGIBLE)
        self.assertEqual(len(rewards), 2)
        self.assertEqual(
            ReferralReward.objects.filter(referral=referral).count(),
            2,
        )
        self.assertFalse(
            ReferralReward.objects.filter(
                referral=referral,
                status=ReferralReward.Status.CREDITED,
            ).exists()
        )

    def test_task_credits_both_rewards_and_preserves_signup_amount_snapshot(self):
        self.create_delivered_order()
        self.offer.reward_amount = Decimal("250.00")
        self.offer.save(update_fields=["reward_amount", "updated_at"])

        result = process_pending_referrals.run()

        self.referral.refresh_from_db()
        rewards = list(ReferralReward.objects.filter(referral=self.referral))
        self.assertEqual(result["processed"], 1)
        self.assertEqual(self.referral.status, Referral.Status.REWARDED)
        self.assertEqual(self.referral.reward_amount, Decimal("100.00"))
        self.assertEqual(len(rewards), 2)
        self.assertTrue(
            all(reward.status == ReferralReward.Status.CREDITED for reward in rewards)
        )
        self.assertTrue(
            all(reward.amount == Decimal("100.00") for reward in rewards)
        )
        for recipient in (self.referrer, self.referred_user):
            wallet = Wallet.objects.get(user=recipient)
            self.assertEqual(wallet.balance, Decimal("100.00"))
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_id__startswith="REFERRAL-REWARD-"
            ).count(),
            2,
        )

    def test_repeated_task_does_not_duplicate_referral_credits(self):
        self.create_delivered_order()

        process_pending_referrals.run()
        process_pending_referrals.run()

        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.Status.REWARDED)
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_id__startswith="REFERRAL-REWARD-"
            ).count(),
            2,
        )
        for recipient in (self.referrer, self.referred_user):
            self.assertEqual(
                Wallet.objects.get(user=recipient).balance,
                Decimal("100.00"),
            )

    def test_failed_reward_is_logged_and_retried_without_duplicate_credit(self):
        self.create_delivered_order()
        _, rewards = process_referral(self.referral.pk)
        retry_reward = rewards[0]
        already_credited_reward = rewards[1]
        real_credit = credit_referral_reward
        attempted_reward_ids = []

        def fail_one_reward(reward_id):
            attempted_reward_ids.append(reward_id)
            if reward_id == retry_reward.pk:
                raise RuntimeError("Temporary referral credit failure")
            return real_credit(reward_id)

        with patch(
            "referrals.tasks.credit_referral_reward",
            side_effect=fail_one_reward,
        ):
            with self.assertLogs("referrals.tasks", level="ERROR") as logs:
                process_pending_referrals.run()

        retry_reward.refresh_from_db()
        already_credited_reward.refresh_from_db()
        self.referral.refresh_from_db()
        self.assertEqual(len(attempted_reward_ids), 2)
        self.assertIn("Temporary referral credit failure", logs.output[0])
        self.assertEqual(retry_reward.status, ReferralReward.Status.PENDING)
        self.assertEqual(
            already_credited_reward.status,
            ReferralReward.Status.CREDITED,
        )
        self.assertEqual(self.referral.status, Referral.Status.ELIGIBLE)

        process_pending_referrals.run()

        retry_reward.refresh_from_db()
        already_credited_reward.refresh_from_db()
        self.referral.refresh_from_db()
        self.assertEqual(retry_reward.status, ReferralReward.Status.CREDITED)
        self.assertEqual(
            already_credited_reward.status,
            ReferralReward.Status.CREDITED,
        )
        self.assertEqual(self.referral.status, Referral.Status.REWARDED)
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_id=f"REFERRAL-REWARD-{already_credited_reward.pk}"
            ).count(),
            1,
        )
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_id__startswith="REFERRAL-REWARD-"
            ).count(),
            2,
        )

    def test_task_does_not_credit_pending_ineligible_or_manual_review_referrals(self):
        ineligible_user = User.objects.create_user(
            email="ineligible-referred@example.com",
            password="test-password",
            full_name="Ineligible Referred User",
            phone="9000000005",
        )
        ineligible_referral = self.create_referral_for(
            ineligible_user,
            "INELIGIBLECODE",
        )
        cancelled_order = self.create_delivered_order(
            user=ineligible_user,
            order_number="TEST-CANCELLED-ORDER",
            status="CANCELLED",
        )

        manual_user = User.objects.create_user(
            email="manual-review-referred@example.com",
            password="test-password",
            full_name="Manual Review Referred User",
            phone="9000000003",
        )
        manual_referral = self.create_referral_for(
            manual_user,
            "MANUALCODE",
        )
        self.create_delivered_order(
            add_delivery_history=False,
            user=manual_user,
            order_number="TEST-MISSING-DELIVERY-HISTORY",
        )

        result = process_pending_referrals.run()

        self.referral.refresh_from_db()
        ineligible_referral.refresh_from_db()
        manual_referral.refresh_from_db()
        cancelled_order.refresh_from_db()
        self.assertEqual(result["processed"], 3)
        self.assertEqual(self.referral.status, Referral.Status.PENDING)
        self.assertEqual(ineligible_referral.status, Referral.Status.INELIGIBLE)
        self.assertEqual(manual_referral.status, Referral.Status.MANUAL_REVIEW)
        self.assertFalse(ReferralReward.objects.exists())
        self.assertFalse(WalletTransaction.objects.exists())

    def test_reprocessing_does_not_duplicate_rewards(self):
        self.create_delivered_order()

        process_referral(self.referral.pk)
        process_referral(self.referral.pk)

        self.assertEqual(
            ReferralReward.objects.filter(referral=self.referral).count(),
            2,
        )

    def test_cancelled_order_after_reward_requires_manual_review(self):
        order = self.create_delivered_order()

        self.referral.qualifying_order = order
        self.referral.status = Referral.Status.REWARDED
        self.referral.save(
            update_fields=["qualifying_order", "status", "updated_at"]
        )

        order.status = "CANCELLED"
        order.save(update_fields=["status", "updated_at"])

        referral = review_credited_referral_for_exceptions(self.referral.pk)

        self.assertEqual(referral.status, Referral.Status.MANUAL_REVIEW)
        self.assertIn(
            "after referral rewards were credited",
            referral.disqualification_reason,
        )

    def test_retry_does_not_credit_wallet_twice(self):
        self.create_delivered_order()
        _, rewards = process_referral(self.referral.pk)
        reward = rewards[0]

        credit_referral_reward(reward.pk)
        credit_referral_reward(reward.pk)

        reward.refresh_from_db()
        self.assertEqual(reward.status, ReferralReward.Status.CREDITED)
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_id=f"REFERRAL-REWARD-{reward.pk}"
            ).count(),
            1,
        )
        self.assertEqual(
            Wallet.objects.get(user=reward.recipient).balance,
            Decimal("100.00"),
        )

    def test_cancelled_order_cannot_receive_referral_reward(self):
        order = self.create_delivered_order()
        _, rewards = process_referral(self.referral.pk)
        reward = rewards[0]

        order.status = "CANCELLED"
        order.save(update_fields=["status", "updated_at"])

        credit_referral_reward(reward.pk)

        self.referral.refresh_from_db()
        self.assertEqual(self.referral.status, Referral.Status.INELIGIBLE)
        self.assertFalse(
            WalletTransaction.objects.filter(
                transaction_id=f"REFERRAL-REWARD-{reward.pk}"
            ).exists()
        )

    def test_admin_can_save_manual_review_note(self):
        # Set up a manual-review referral and an admin test user.
        self.referral.status = Referral.Status.MANUAL_REVIEW
        self.referral.save(update_fields=["status", "updated_at"])

        self.referrer.is_staff = True
        self.referrer.is_superuser = True
        self.referrer.save(update_fields=["is_staff", "is_superuser"])

        self.client.force_login(self.referrer)

        response = self.client.post(
            reverse("referrals:admin_referrals_page"),
            {
                "action": "save_review_note",
                "referral_id": self.referral.pk,
                "review_note": "Verified test review note.",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.referral.refresh_from_db()
        self.assertIn("Verified test review note.", self.referral.disqualification_reason)
        self.assertIn(self.referrer.email, self.referral.disqualification_reason)
