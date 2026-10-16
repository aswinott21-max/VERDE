from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.conf import settings

from wallet.models import Wallet, WalletTransaction, WalletTopUp

from wallet.services.wallet_service import credit_wallet
from checkout.services.razorpay_service import (create_razorpay_topup_order,verify_razorpay_payment,verify_captured_payment)

import logging
logger = logging.getLogger(__name__)
# Create your views here.

@login_required
def my_wallet(request):
    wallet = Wallet.objects.filter(user=request.user).first()

    if wallet is None:
        wallet = Wallet.objects.create(user=request.user)

    transactions = (WalletTransaction.objects.filter(wallet=wallet)
                    if wallet
                    else WalletTransaction.objects.none())
    transaction_type = request.GET.get("type", "").strip()
    search_id = request.GET.get("search", "").strip()
    date_range = request.GET.get("date_range", "").strip()

    # Filter transactions by credit or debit type when selected.
    if transaction_type in ["CREDIT", "DEBIT"]:
        transactions = transactions.filter(transaction_type=transaction_type)


    today = timezone.localdate()
    if date_range in ["7", "30", "90"]:
        start_date = today - timedelta(days=int(date_range) - 1)
        transactions = transactions.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=today,
        )
    # Search by transaction ID or exact amount when the input is numeric.
    if search_id:
        search_filter = Q(transaction_id__icontains=search_id)

        try:
            search_amount = Decimal(search_id)
            if search_amount.is_finite():
                search_filter |= Q(amount=search_amount)
        except InvalidOperation:
            pass

        transactions = transactions.filter(search_filter)

    #calculate total credits and debits across all transactions, regardless of filters.

    summary_transactions =(
        WalletTransaction.objects.filter(wallet=wallet)
        if wallet
        else WalletTransaction.objects.none())
    totals = summary_transactions.aggregate(
        total_added=Sum("amount", filter=Q(transaction_type="CREDIT")),
        total_spent=Sum("amount", filter=Q(transaction_type="DEBIT")),
    )

    context= {
        "wallet": wallet,
        "transactions": transactions,
        "total_added": totals["total_added"] or 0,
        "total_spent": totals["total_spent"] or 0,
        "transaction_type": transaction_type,
        "search_id": search_id,
        "date_range": date_range,
    }

    
    return render(request, "wallet/my_wallet.html", context)


@login_required
@require_POST
@never_cache
def create_wallet_topup(request):
    raw_amount = request.POST.get("amount", "").strip()

    try:
        amount = Decimal(raw_amount)
        if not amount.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return JsonResponse({"error":"Enter a valid top-up amount"}, status=400)

    if amount < Decimal("100.00") or amount> Decimal("10000.00"):
        return JsonResponse({"error":"Top-up amount must be between ₹100 and ₹10,000"},status=400)
    if amount != amount.quantize(Decimal("0.00")):
        return JsonResponse({"error": "Amount can have at most two decimal places."},status=400)

    wallet,created =Wallet.objects.get_or_create(user=request.user)

    if not wallet.is_active:
        return  JsonResponse({"error": "Your wallet is inactive."},status=400)

    import uuid
    receipt = f"wallet - {uuid.uuid4().hex}"

    try:
        razorpay_order = create_razorpay_topup_order(amount, receipt)

        topup = WalletTopUp.objects.create(
            user=request.user,
            amount=amount,
            razorpay_order_id=razorpay_order["id"],
            status="PENDING",
        )
    except Exception:

        logger.exception("Could not create wallet top-up order for user %s",request.user.pk,)
        return JsonResponse({"error": "Unable to start the top-up. Please try again."},status = 502)

    return JsonResponse(
        {
            "topup_id": topup.pk,
            "razorpay_order_id": razorpay_order["id"],
            "amount": int(amount * 100),
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
        }
    )

@login_required
@require_POST
@never_cache
def verify_wallet_topup(request):

    razorpay_order_id = request.POST.get("razorpay_order_id","").strip()
    razorpay_payment_id = request.POST.get("razorpay_payment_id","").strip()
    razorpay_signature = request.POST.get("razorpay_signature", "").strip()

    if not all((razorpay_order_id,razorpay_payment_id, razorpay_signature)):
        return JsonResponse({"error": "Payment verification details are incomplete."},status=400)

    try:
        topup = WalletTopUp.objects.get(user=request.user, razorpay_order_id=razorpay_order_id)

        with transaction.atomic():
            topup = WalletTopUp.objects.select_for_update().get(pk=topup.pk, user= request.user)

            #verify the razorpay signature before checking payment status
            if not verify_razorpay_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
                return JsonResponse({"error": "Payment signature verification failed."}, status=400)

            if topup.status == "COMPLETED":
                if topup.razorpay_payment_id == razorpay_payment_id:
                    return JsonResponse({"message": "This top-up has already been credited."})
                return JsonResponse({"error": "This top-up has already been processed."}, status=400)

            if topup.status != "PENDING":
                return JsonResponse({"error": "This top-up is not pending."}, status=400)

            if not verify_captured_payment(razorpay_payment_id, topup.razorpay_order_id, topup.amount):
                return JsonResponse({"error": "The payment has not been confirmed as captured."}, status=400)

            credit_wallet(user=request.user,amount=topup.amount,reference_id=topup.razorpay_order_id,transaction_id=razorpay_payment_id,)
            topup.razorpay_payment_id = razorpay_payment_id
            topup.status = "COMPLETED"
            topup.save(update_fields=["razorpay_payment_id","status","updated_at",])

    except WalletTopUp.DoesNotExist:
        logger.warning( "Wallet top-up order not found for user %s", request.user.pk)
        return JsonResponse({"error": "Wallet top-up order not found."},status=404)

    except Exception:
        logger.exception("Wallet top-up verification failed for user %s",request.user.pk)

        return JsonResponse({"error": "Unable to verify the payment right now. Please try again."},status=500)

    return JsonResponse({"message": "Wallet topped up successfully."})
