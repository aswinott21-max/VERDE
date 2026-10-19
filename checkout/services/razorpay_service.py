import logging
import razorpay
from django.conf import settings

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
    
