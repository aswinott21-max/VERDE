import secrets
import string
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from orders.models import Order, Refund, Return
from wallet.models import WalletTransaction
from .models import Referral, ReferralCode, ReferralReward

from wallet.services.wallet_service import credit_wallet


def generate_referral_code(user):
    #Return the customer's existing code or create a unique one
    existing_code = ReferralCode.objects.filter(user=user).first()
    if existing_code:
        return existing_code
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(8))

        if not ReferralCode.objects.filter(code=code).exists():
            return ReferralCode.objects.create(user=user,code=code)

def evaluate_referral_eligibility(referral):
    #determine whether a referral qualifies for its wallet rewards

    if referral.status in {Referral.Status.REWARDED,Referral.Status.INELIGIBLE,Referral.Status.MANUAL_REVIEW}:
        return referral.status, "Referral is already finalized or required review"

    #find the referred customer's earliest successfully paid order
    order = (Order.objects.filter(user_id=referral.referred_user_id, payment_status="PAID").order_by("created_at","pk").first())

    if not order:
        return Referral.Status.PENDING, "No successfully paid order yet"

    referral.qualifying_order = order
    referral.save(update_fields=["qualifying_order", "updated_at"])

    if order.status in {"CANCELLED", "RETURNED"}:
        return Referral.Status.INELIGIBLE, "The qualifying order was cancelled or returned"
    if order.items.filter(item_status="CANCELLED").exists():
        return Referral.Status.INELIGIBLE, "An item in the qualifying order was cancelled."

    # A completed refund or approved return disqualifies the referral.
    if Refund.objects.filter(
        return_request__order_item__order=order,
        status="COMPLETED",
    ).exists() or Return.objects.filter(
        order_item__order=order,
        status="INSPECT_APPROVED",
    ).exists():
        return Referral.Status.INELIGIBLE, "The qualifying order has a processed return or refund."

    # Do not reward an order before delivery.
    if order.status != "DELIVERED":
        return Referral.Status.PENDING, "The qualifying order has not been delivered."

    delivery_history = (
        order.status_history.filter(status="DELIVERED")
        .order_by("created_at")
        .first()
    )

    if not delivery_history:
        return Referral.Status.MANUAL_REVIEW, "Delivery history is missing."

    #the return window includes the delivery date and following three calendar days
    delivery_date = timezone.localdate(delivery_history.created_at)
    last_return_date = delivery_date + timedelta(days=3)

    if timezone.localdate() <= last_return_date:
        return Referral.Status.PENDING, "The three-day return window is still open."

    #unresolved return requests must not be rewarded automatically
    unresolved_return = Return.objects.filter(order_item__order=order,status__in=["REQUESTED", "PICKED"],).exists()

    if unresolved_return:
        return Referral.Status.MANUAL_REVIEW, "A return request remains unresolved."

    return Referral.Status.ELIGIBLE, ""


@transaction.atomic
def credit_referral_reward(reward_id):
    #Credit one referral reward safely and support retries

    reward = (ReferralReward.objects.select_for_update().select_related("referral", "recipient").get(pk=reward_id))

    if reward.status == ReferralReward.Status.CREDITED:
        if reward.wallet_transaction_id:
            return reward

        reward.status = ReferralReward.Status.MANUAL_REVIEW
        reward.review_note = "Marked credited without a linked wallet transaction."
        reward.save(update_fields=["status", "review_note", "updated_at"])

    if reward.status == ReferralReward.Status.MANUAL_REVIEW:
        return reward

    # Recheck eligibility before crediting the wallet.
    referral = Referral.objects.select_for_update().get(
        pk=reward.referral_id
    )

    if referral.status != Referral.Status.ELIGIBLE:
        return reward

    status, reason = evaluate_referral_eligibility(referral)

    if status != Referral.Status.ELIGIBLE:
        # Require manual review if a partner reward was already credited.
        has_credited_reward = ReferralReward.objects.filter(
            referral=referral,
            status=ReferralReward.Status.CREDITED,
        ).exists()

        referral.status = (
            Referral.Status.MANUAL_REVIEW
            if has_credited_reward
            else status
        )
        referral.disqualification_reason = reason
        referral.save(
            update_fields=[
                "status",
                "disqualification_reason",
                "updated_at",
            ]
        )
        return reward

    transaction_id = f"REFERRAL-REWARD-{reward.pk}"

    #reconcile an existing credit before attempting another one
    wallet_transaction = WalletTransaction.objects.select_related("wallet").filter(transaction_id=transaction_id).first()

    if wallet_transaction:
        if (
            wallet_transaction.wallet.user_id != reward.recipient_id
            or wallet_transaction.amount != reward.amount
            or wallet_transaction.transaction_type != "CREDIT"
        ):
            reward.status = ReferralReward.Status.MANUAL_REVIEW
            reward.review_note = "Existing wallet transaction does not match this reward."
            reward.save(update_fields=["status", "review_note", "updated_at"])

            referral = Referral.objects.select_for_update().get(
                pk=reward.referral_id
            )
            referral.status = Referral.Status.MANUAL_REVIEW
            referral.save(update_fields=["status", "updated_at"])
            return reward
    else:
        try:
            credit_wallet(
                user=reward.recipient,
                amount=reward.amount,
                reference_id=f"Referral reward #{reward.pk}",
                transaction_id=transaction_id,
            )
        except ValueError as exc:
            reward.status = ReferralReward.Status.MANUAL_REVIEW
            reward.review_note = str(exc)
            reward.save(update_fields=["status", "review_note", "updated_at"])

            referral = Referral.objects.select_for_update().get(
                pk=reward.referral_id
            )
            referral.status = Referral.Status.MANUAL_REVIEW
            referral.save(update_fields=["status", "updated_at"])
            return reward

        wallet_transaction = WalletTransaction.objects.get(
            transaction_id=transaction_id
        )

    reward.wallet_transaction = wallet_transaction
    reward.status = ReferralReward.Status.CREDITED
    reward.credited_at = wallet_transaction.created_at
    reward.review_note = ""
    reward.save(
        update_fields=[
            "wallet_transaction",
            "status",
            "credited_at",
            "review_note",
            "updated_at",
        ]
    )

    # Finalize the referral only after both recipient rewards are credited.
    referral = Referral.objects.select_for_update().get(pk=reward.referral_id)
    rewards = ReferralReward.objects.filter(referral=referral)

    if (
        rewards.count() == 2
        and not rewards.exclude(status=ReferralReward.Status.CREDITED).exists()
    ):
        referral.status = Referral.Status.REWARDED
        referral.save(update_fields=["status", "updated_at"])

    return reward



@transaction.atomic
def create_referral_rewards(referral_id):
    #create one pending reward for each referral participant
    referral = Referral.objects.select_for_update().get(pk=referral_id)

    if referral.status != Referral.Status.ELIGIBLE:
        return []

    rewards = []

    recipients = [
        (referral.referrer, ReferralReward.RecipientRole.REFERRER),
        (referral.referred_user, ReferralReward.RecipientRole.REFERRED),
    ]

    for recipient, role in recipients:
        reward, created = ReferralReward.objects.get_or_create(
            referral=referral,
            recipient_role=role,
            defaults={
                "recipient": recipient,
                "amount": referral.reward_amount,
                "status": ReferralReward.Status.PENDING,
            },
        )

        #existing records must match the original referral snapshot
        if (
            reward.recipient_id != recipient.pk
            or reward.amount != referral.reward_amount
        ):
            referral.status = Referral.Status.MANUAL_REVIEW
            referral.save(update_fields=["status", "updated_at"])
            return []

        rewards.append(reward)

    return rewards


@transaction.atomic
def process_referral(referral_id):
    #Evaluate a referral and create rewards when eligible
    referral = Referral.objects.select_for_update().get(pk=referral_id)

    #Do not automatically reopen finalized referrals
    if referral.status in {
        Referral.Status.REWARDED,
        Referral.Status.INELIGIBLE,
        Referral.Status.MANUAL_REVIEW,
    }:
        return referral, []

    status, reason = evaluate_referral_eligibility(referral)

    referral.status = status
    referral.disqualification_reason = (
        reason
        if status in {
            Referral.Status.INELIGIBLE,
            Referral.Status.MANUAL_REVIEW,
        }
        else ""
    )
    referral.save(
        update_fields=["status", "disqualification_reason", "updated_at"]
    )

    if status != Referral.Status.ELIGIBLE:
        return referral, []

    rewards = create_referral_rewards(referral.pk)
    referral.refresh_from_db()

    return referral, rewards



@transaction.atomic
def review_credited_referral_for_exceptions(referral_id):
    #flag post-reward order exceptions for manual review

    referral = (
        Referral.objects.select_for_update(of=("self",))
        .select_related("qualifying_order")
        .get(pk=referral_id)
    )

    if referral.status != Referral.Status.REWARDED:
        return referral

    order = referral.qualifying_order

    if not order:
        referral.status = Referral.Status.MANUAL_REVIEW
        referral.disqualification_reason = (
            "Rewarded referral has no qualifying order."
        )
        referral.save(
            update_fields=[
                "status",
                "disqualification_reason",
                "updated_at",
            ]
        )
        return referral

    exception_found = (
        order.status in {"CANCELLED", "RETURNED"}
        or order.items.filter(
            item_status__in=["CANCELLED", "RETURNED"]
        ).exists()
        or Refund.objects.filter(
            return_request__order_item__order=order,
            status="COMPLETED",
        ).exists()
        or Return.objects.filter(
            order_item__order=order,
            status="INSPECT_APPROVED",
        ).exists()
    )

    if exception_found:
        referral.status = Referral.Status.MANUAL_REVIEW
        referral.disqualification_reason = (
            "The qualifying order was cancelled, returned, or refunded "
            "after referral rewards were credited. Review wallet credits "
            "manually; do not reverse them automatically."
        )
        referral.save(
            update_fields=[
                "status",
                "disqualification_reason",
                "updated_at",
            ]
        )

    return referral
