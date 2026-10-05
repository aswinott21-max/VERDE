import logging

from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.db.models import Q
from django.core.paginator import Paginator
from adminpanel.decorators import admin_required
from coupons.models import Coupon
from django.shortcuts import redirect
from coupons.forms import CouponForm

logger = logging.getLogger(__name__)

@never_cache
@admin_required
def admin_coupons_page(request):

    search = request.GET.get("search","").strip()
    coupons = Coupon.objects.all()

    if search:
        coupons=  coupons.filter(Q(coupon_name__icontains=search) | Q(code__icontains=search))

    coupons = coupons.order_by("-created_at")

    pagianator = Paginator(coupons,7)

    page_number = request.GET.get("page")

    coupons = pagianator.get_page(page_number)

    logger.info("Loaded %s coupons for  admin coupon managemet.", coupons.paginator.count,)

    coupon_form_data = request.session.pop("coupon_form_data",None)
    coupon_form_errors = request.session.pop("coupon_form_errors",None)

    if coupon_form_data:
        coupon_form = CouponForm(coupon_form_data)

        if coupon_form_errors:
            for field_name, errors in coupon_form_errors.items():
                for error in errors:
                    coupon_form.add_error(field_name,error["message"],)
    else:
        coupon_form = CouponForm()

    return render(request,"coupons/admin_coupons.html",{"coupons":coupons,"search":search, "coupon_form":coupon_form},)


@never_cache
@admin_required
def add_coupon(request):

    if request.method != "POST":
       return redirect("admin_coupons_page")

    form = CouponForm(request.POST)

    if form.is_valid():
        coupon = form.save()

        logger.info("Coupon %s created successfully.", coupon.code,)

        return redirect("admin_coupons_page")
    logger.warning("Invalid coupon form submitted: %s", form.errors,)
    request.session["coupon_form_data"] = request.POST.dict() 
    request.session["coupon_form_errors"] = form.errors.get_json_data()
    return redirect("admin_coupons_page")


@never_cache
@admin_required
def edit_coupon(request, coupon_id):
    if request.method != "POST":
        return redirect("admin_coupons_page")

    coupon = Coupon.objects.get(id=coupon_id)

    form = CouponForm(request.POST,instance=coupon)

    if form.is_valid():
        coupon = form.save()

        logger.info("Coupon %s updated successfully.",coupon.code)
    return redirect ("admin_coupons_page")


@never_cache
@admin_required
def toggle_coupon_status(request, coupon_id):

    if request.method != "POST":
        return redirect("admin_coupon_page")

    coupon = Coupon.objects.get(id=coupon_id)

    if coupon.status == "active":
        coupon.status = "disabled"
        logger.info("Coupon %s disabled successfully.", coupon.code)

    else:
        coupon.status = "active"
        logger.info("Coupon %s enabled successfully.", coupon.code)

    coupon.save(update_fields=["status","updated_at"])
    return redirect("admin_coupons_page")

