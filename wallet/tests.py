from decimal import Decimal

from django.test import TestCase

from users.models import User
from wallet.models import Wallet, WalletTransaction
from wallet.services.wallet_service import credit_wallet


class WalletServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="wallet-test@example.com",
            full_name="Wallet Test",
            phone="1234567890",
            password="test-password",
        )
        self.wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal("100.00"),
        )

    def test_credit_wallet_increases_balance_and_records_transaction(self):
        # Verify a credit updates the balance and records its transaction.
        wallet = credit_wallet(
            user=self.user,
            amount=Decimal("50.00"),
            reference_id="TEST-ORDER-001",
            transaction_id="TEST-CREDIT-001",
        )

        self.wallet.refresh_from_db()
        transaction_record = WalletTransaction.objects.get(
            transaction_id="TEST-CREDIT-001"
        )

        self.assertEqual(wallet.balance, Decimal("150.00"))
        self.assertEqual(self.wallet.balance, Decimal("150.00"))
        self.assertEqual(transaction_record.amount, Decimal("50.00"))
        self.assertEqual(transaction_record.balance_after, Decimal("150.00"))
        self.assertEqual(transaction_record.transaction_type, "CREDIT")


    def test_debit_wallet_decreases_balance_and_records_transaction(self):
        # Verify a debit updates the balance and records its transaction.
        from wallet.services.wallet_service import debit_wallet

        wallet = debit_wallet(
            user=self.user,
            amount=Decimal("30.00"),
            reference_id="TEST-ORDER-002",
            transaction_id="TEST-DEBIT-001",
        )

        self.wallet.refresh_from_db()
        transaction_record = WalletTransaction.objects.get(
            transaction_id="TEST-DEBIT-001"
        )

        self.assertEqual(wallet.balance, Decimal("70.00"))
        self.assertEqual(self.wallet.balance, Decimal("70.00"))
        self.assertEqual(transaction_record.amount, Decimal("30.00"))
        self.assertEqual(transaction_record.balance_after, Decimal("70.00"))
        self.assertEqual(transaction_record.transaction_type, "DEBIT")


    def test_debit_wallet_rejects_insufficient_balance(self):
        # Verify insufficient funds leave the wallet unchanged.
        from wallet.services.wallet_service import debit_wallet

        with self.assertRaisesMessage(
            ValueError, "Insufficient wallet balance."
        ):
            debit_wallet(
                user=self.user,
                amount=Decimal("150.00"),
                reference_id="TEST-ORDER-003",
                transaction_id="TEST-DEBIT-002",
            )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("100.00"))
        self.assertFalse(
            WalletTransaction.objects.filter(
                transaction_id="TEST-DEBIT-002"
            ).exists()
        )

    def test_credit_wallet_rejects_non_positive_amounts(self):
        # Verify zero and negative credits do not change the wallet.
        for amount in (Decimal("0.00"), Decimal("-10.00")):
            with self.subTest(amount=amount):
                with self.assertRaisesMessage(
                    ValueError, "Credit amount must be greater than zero."
                ):
                    credit_wallet(
                        user=self.user,
                        amount=amount,
                        reference_id="TEST-INVALID-CREDIT",
                        transaction_id=f"TEST-CREDIT-INVALID-{amount}",
                    )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("100.00"))
        self.assertEqual(self.wallet.transactions.count(), 0)

    def test_credit_wallet_rejects_duplicate_transaction_id(self):
        # Verify a duplicate transaction cannot credit the wallet twice.
        credit_wallet(
            user=self.user,
            amount=Decimal("50.00"),
            reference_id="TEST-ORDER-DUPLICATE",
            transaction_id="TEST-CREDIT-DUPLICATE",
        )

        with self.assertRaisesMessage(
            ValueError, "This wallet transaction already exists."
        ):
            credit_wallet(
                user=self.user,
                amount=Decimal("50.00"),
                reference_id="TEST-ORDER-DUPLICATE",
                transaction_id="TEST-CREDIT-DUPLICATE",
            )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("150.00"))
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_id="TEST-CREDIT-DUPLICATE"
            ).count(),
            1,
        )


    def test_debit_wallet_rejects_duplicate_transaction_id(self):
        # Verify a duplicate transaction cannot debit the wallet twice.
        from wallet.services.wallet_service import debit_wallet

        debit_wallet(
            user=self.user,
            amount=Decimal("30.00"),
            reference_id="TEST-ORDER-DUPLICATE-DEBIT",
            transaction_id="TEST-DEBIT-DUPLICATE",
        )

        with self.assertRaisesMessage(
            ValueError, "This wallet transaction already exists."
        ):
            debit_wallet(
                user=self.user,
                amount=Decimal("30.00"),
                reference_id="TEST-ORDER-DUPLICATE-DEBIT",
                transaction_id="TEST-DEBIT-DUPLICATE",
            )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("70.00"))
        self.assertEqual(
            WalletTransaction.objects.filter(
                transaction_id="TEST-DEBIT-DUPLICATE"
            ).count(),
            1,
        )

    def test_credit_wallet_rejects_inactive_wallet(self):
        # Verify an inactive wallet cannot receive credits.
        self.wallet.is_active = False
        self.wallet.save(update_fields=["is_active"])

        with self.assertRaisesMessage(
            ValueError, "The user's wallet is inactive."
        ):
            credit_wallet(
                user=self.user,
                amount=Decimal("50.00"),
                reference_id="TEST-INACTIVE-WALLET",
                transaction_id="TEST-CREDIT-INACTIVE",
            )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("100.00"))
        self.assertFalse(
            WalletTransaction.objects.filter(
                transaction_id="TEST-CREDIT-INACTIVE"
            ).exists()
        )

    def test_debit_wallet_rejects_inactive_wallet(self):
        # Verify an inactive wallet cannot be debited.
        from wallet.services.wallet_service import debit_wallet

        self.wallet.is_active = False
        self.wallet.save(update_fields=["is_active"])

        with self.assertRaisesMessage(
            ValueError, "Active wallet not found."
        ):
            debit_wallet(
                user=self.user,
                amount=Decimal("30.00"),
                reference_id="TEST-INACTIVE-DEBIT",
                transaction_id="TEST-DEBIT-INACTIVE",
            )

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("100.00"))
        self.assertFalse(
            WalletTransaction.objects.filter(
                transaction_id="TEST-DEBIT-INACTIVE"
            ).exists()
        )


    def test_credit_wallet_creates_wallet_if_missing(self):
        # Verify credit creates a wallet for a user without one.
        self.wallet.delete()

        wallet = credit_wallet(
            user=self.user,
            amount=Decimal("50.00"),
            reference_id="TEST-NEW-WALLET",
            transaction_id="TEST-CREDIT-NEW-WALLET",
        )

        self.assertEqual(wallet.balance, Decimal("50.00"))
        self.assertTrue(
            WalletTransaction.objects.filter(
                wallet=wallet,
                transaction_id="TEST-CREDIT-NEW-WALLET",
            ).exists()
        )