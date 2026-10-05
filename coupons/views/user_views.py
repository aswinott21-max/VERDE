import logging

from django.shortcuts import render
from django.views.decorators.cache import never_cache

from coupons.models import Coupon
from coupons.services.coupon_service import is_coupon_valid

logger = logging.getLogger(__name__)

@never_cache
def user_coupons_page(request):
    coupons = Coupon.objects.all().order_by("-created_at")

    #Keep valid coupon
    valid_coupon =[
        coupon for coupon in coupons
        if is_coupon_valid(coupon)
    ]

    logger.info("Loaded %s valid coupons for user coupon page.", len(valid_coupon),)

    return render(request,"coupons/user_coupons.html",{"coupons":valid_coupon,})

