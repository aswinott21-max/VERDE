import logging
import razorpay
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)

def get_razorpay_client():

    #create razorpay client using the API credentials
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise ValueError("Razorpay credentials are not configured.")
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID,settings.RAZORPAY_KEY_SECRET,))

def create_razorpay_order(order):

    #create razor pay order for the amount stored in the local order
    client = get_razorpay_client()

    #amount in small currency unit
    amount_in_paise = int(order.total_amount * 100)

    if amount_in_paise <=0:
        raise ValueError("Order amount must be greater than zero")

    razorpay_order = client.order.create(
        data = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": order.order_number,
        }
    ) 
    logger.info("Razor order created for local order %s", order.order_number,)

    return razorpay_order


def create_razorpay_topup_order(amount, receipt):

    amount= Decimal(str(amount))

    amount_in_paise = int(amount*100)

    if amount <=0 or amount * 100 != amount_in_paise:
        raise ValueError("Top-up amount must be posistive and have at most two decimal places ")

    client = get_razorpay_client()
    razorpay_order = client.order.create(
        data={
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": receipt,
        }
    )

    logger.info("Razorpay wallet top-up order created: %s", receipt)

    return razorpay_order



def verify_razorpay_payment(razorpay_order_id, razorpay_payment_id,razorpay_signature):
    #Verify the payment credential match razorpay creden
    client = get_razorpay_client()

    #reject incomplete payment details before signature verification 
    if not all((razorpay_order_id,razorpay_payment_id,razorpay_signature)):
        return False

    try:
        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )

    except razorpay.errors.SignatureVerificationError:
        logger.warning("Razorpay signature verification failed for order %s",razorpay_order_id)

        return False
    return True


def verify_captured_payment(razorpay_payment_id, expected_order_id, expected_amount):

    client = get_razorpay_client()

    expected_amount_paise = int(Decimal(str(expected_amount))*100)

    try:
        payment = client.payment.fetch(razorpay_payment_id)

    except Exception:
        logger.exception("Could not fetch Razorpay payment %s", razorpay_payment_id)
        raise

    #confirm the payment status, order ID, amount, and currency
    is_valid = (
        payment.get("status") == "captured"
        and payment.get("order_id") == expected_order_id
        and payment.get("amount") == expected_amount_paise
        and payment.get("currency") == "INR"
    )

    if not is_valid:
        logger.warning("Razorpay payment verification mismatch for payment %s", razorpay_payment_id)

    return is_valid
