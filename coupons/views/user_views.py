import logging

from django.shortcuts import render
from django.views.decorators.cache import never_cache

from coupons.models import Coupon, CouponUsage
from coupons.services.coupon_service import is_coupon_valid,is_coupon_usage_available

logger = logging.getLogger(__name__)


@never_cache
def user_coupons_page(request):
    
    coupons = Coupon.objects.all().order_by("-created_at")

    valid_coupon = [
        coupon for coupon in coupons
        if is_coupon_valid(coupon)
        and is_coupon_usage_available(coupon)
    ]

    used_coupon_ids = set()
    user_coupons_ids = set()

    if request.user.is_authenticated:
        user_coupons_ids = set(CouponUsage.objects.filter(user=request.user,coupon__in=valid_coupon,).values_list("coupon_id", flat=True))
        used_coupon_ids = user_coupons_ids

    logger.info("Loaded %s valid coupons for user coupon page.",len(valid_coupon),)

    return render(request, "coupons/user_coupons.html", {
        "coupons": valid_coupon,
        "used_coupon_ids": used_coupon_ids,
        "user_coupons_ids": user_coupons_ids,
    })

