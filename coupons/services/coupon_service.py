import logging
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.utils import timezone

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def is_coupon_valid(coupon):
    #cheke coupon valid now
    now = timezone.now().astimezone(IST)
    
    if coupon.status != "active":
        logger.info("Coupon %s is disabled.", coupon.code,)
        return False
    if now < coupon.start_date:
        logger.info("Coupon %is not active yet.",coupon.code,)
        return False
    if now > coupon.expiry_date:
        logger.info("Coupon %s has expired.", coupon.code)
        return False
    
    logger.info("Coupon %s is currently valid", coupon.code)
    return True

def is_coupon_usage_available(coupon):
    #Check coupon is still available

    if coupon.usage_limit is None:
        logger.info("Coupon % has no usage limit.", coupon.code)
        return True
    if coupon.used_count >= coupon.usage_limit:
        logger.info("Coupon has reached its usage limit",coupon.code)
        return False
    return True

def is_minimum_order_amount_met(coupon, order_amount):
    #check order amount meet minimum order amount

    if order_amount < coupon.minimum_order_amount:
        logger.info("Coupon %s requires a minimum order amount of %s. ", "Current order amount is %s.", coupon.code,coupon.minimum_order_amount,order_amount)
        return False
    return True

def calculate_coupon_discount(coupon, order_amount):
    #calculate the discount amount for coupon

    order_amount = Decimal(order_amount)
    if coupon.discount_type == "percentage":
        discount_amount = (order_amount*coupon.discount_value)/Decimal("100")
        if (coupon.max_discount_amount is not None and discount_amount > coupon.max_discount_amount):
            discount_amount= coupon.max_discount_amount
    elif coupon.discount_type == "fixed":
        discount_amount = coupon.discount_value
    else:
        logger.warning("Unknown discount type '%s' for coupon %s.", coupon.discount_type,coupon.code)
        return Decimal("0.00")
        
    #Discount should not be never greater than order amount
    if discount_amount > order_amount:
        discount_amount = order_amount

    return discount_amount.quantize(Decimal("0.01"))

