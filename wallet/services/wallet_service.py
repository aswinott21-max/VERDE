from decimal import Decimal
from django.db import transaction

from wallet.models import Wallet, WalletTransaction


@transaction.atomic
def get_or_create_wallet(user):
    #retrieve or create 
    wallet, created = Wallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def credit_wallet(user, amount, reference_id, transaction_id):
    #credit a positive amount once and record the resulting balance
    amount = Decimal(str(amount))

    if amount <= 0:
        raise ValueError("Credit amount must be greater than zero.")

    if WalletTransaction.objects.filter(transaction_id=transaction_id).exists():
        raise ValueError("This wallet transaction already exists.")

    wallet = Wallet.objects.select_for_update().filter(user=user,is_active=True,).first()

    if not wallet:
        existing_wallet = Wallet.objects.filter(user=user).first()

        if existing_wallet:
            raise ValueError("The user's wallet is inactive.")

        wallet = Wallet.objects.create(user=user)

    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    wallet.balance += amount
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        amount=amount,
        balance_after=wallet.balance,
        reference_id=str(reference_id),
        transaction_id=transaction_id,
        transaction_type="CREDIT",
    )

    return wallet


@transaction.atomic
def debit_wallet(user, amount, reference_id, transaction_id):
    #deduct a positive amount only when the wallet has sufficient funds.
    amount = Decimal(str(amount))

    if amount <= 0:
        raise ValueError("Debit amount must be greater than zero.")

    if WalletTransaction.objects.filter(transaction_id=transaction_id).exists():
        raise ValueError("This wallet transaction already exists.")

    wallet = Wallet.objects.select_for_update().filter(user=user,is_active=True,).first()

    if not wallet:
        raise ValueError("Active wallet not found.")

    if wallet.balance < amount:
        raise ValueError("Insufficient wallet balance.")

    wallet.balance -= amount
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        amount=amount,
        balance_after=wallet.balance,
        reference_id=str(reference_id),
        transaction_id=transaction_id,
        transaction_type="DEBIT",
    )

    return wallet
