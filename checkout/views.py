import logging
import json
from django.shortcuts import render,redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.db import transaction

from users.models import Address
from coupons.models import Coupon


from django.conf import settings

from cart.services.cart_service import get_cart_details
from checkout.services.checkout_service import create_order,create_pending_razorpay_order,finalize_razorpay_order, validate_checkout_coupon,calculate_coupon_eligible_subtotal
from checkout.services.razorpay_service import create_razorpay_order,verify_razorpay_payment

# Create your views here.

logger = logging.getLogger(__name__)


@login_required
@never_cache
def checkout_page(request):
    cart_data = get_cart_details(request.user)

    for item in cart_data["items"]:
        product = item["product"]
        quantity = item["quantity"]

        if product.variants.exists():
            variant = item.get("variant")

            if not variant or not variant.is_active or variant.stock_quantity < quantity:
                from django.contrib import messages
                messages.error(request, f"Insufficient stock for {product.name}. Please update your cart.")
                return redirect("cart:cart_page")
        elif not product.is_active or product.stock_quantity < quantity:
            from django.contrib import messages
            messages.error(request, f"Insufficient stock for {product.name}. Please update your cart.")
            return redirect("cart:cart_page")

    addresses = Address.objects.filter(user=request.user).order_by("-is_default", "-created_at")

    coupon = None
    coupon_discount = 0

    coupon_id = request.session.get("checkout_coupon_id")

    if coupon_id:
        from checkout.services.checkout_service import validate_checkout_coupon

        selected_coupon = Coupon.objects.filter(id=coupon_id).first()

        if selected_coupon:
            eligible_subtotal = calculate_coupon_eligible_subtotal(
                (item["product"], item["item_total"])
                for item in cart_data["items"])

            coupon, coupon_discount, error = validate_checkout_coupon(selected_coupon.code, eligible_subtotal, request.user)
            #remove invalid coupon from session to prevent stale discount
            if error:
                request.session.pop("checkout_coupon_id", None)
                coupon = None
                coupon_discount = 0

        else:
            request.session.pop("checkout_coupon_id",None)#clear the session if the selected no longer exists.


    logger.info("Checkout page opened by user: %s with %s cart items",request.user,len(cart_data["items"]),)

    return render(request,"checkout/checkout.html",{"cart_data": cart_data, "addresses": addresses,"coupon":coupon, "coupon_discount":coupon_discount},)



@login_required
@require_POST
@never_cache
def place_order(request):
    data =json.loads(request.body)

    address_id = data.get("address_id")
    delivery_method = data.get("delivery_method")
    payment_method = data.get("payment_method")

    if not address_id:
        return JsonResponse({"message":"Please select a deivery address."},status=400)

    if not delivery_method:
        return JsonResponse({"message":"PLease select a delivery method"}, status=400)
    if not payment_method:
        return JsonResponse({"message":"Please select a payment method"}, status=400)

    order, error = create_order(
        user=request.user,
        address_id=address_id,
        delivery_method=delivery_method,
        payment_method=payment_method,
        coupon_id=request.session.get("checkout_coupon_id"),
    )

    if error:
        # Clear the selected coupon only when coupon validation fails.
        coupon_errors = {
            "Coupon code not found",
            "This coupon is inactive or expired",
            "You have already used this coupon",
            "This coupon has reached its usage limit",
            "Select coupon was not found",
        }

        if error in coupon_errors or error.startswith(
            "Minimal product subtotal for this coupon is ₹"
        ):
            request.session.pop("checkout_coupon_id", None)

        return JsonResponse({"message": error}, status=400)

    return JsonResponse({"message":"Order placed successfully", "order_number":order.order_number}, status=201)


@login_required
@require_POST
@never_cache
def create_razorpay_payment(request):
    data = json.loads(request.body)
    address_id = data.get("address_id")
    delivery_method = data.get("delivery_method")

    if not address_id or not delivery_method:
        return JsonResponse(
            {"method":"Address and delivery method are required"},status=400)


    #create the local order without deducting stock or clearing the cart
    order, error = create_pending_razorpay_order(user=request.user,address_id=address_id,delivery_method=delivery_method,coupon_id=request.session.get("checkout_coupon_id"),)

    if error:
        return JsonResponse({"message":error}, status=400)
    try:
        #create the correspondign order in razorpay
        razorpay_order = create_razorpay_order(order)
    except Exception:
        logger.exception("Failed to create Razorpay order for %s", order.order_number)
        return JsonResponse({"message" : "Unable to start payment. Please try again"},status=502)

    #save the razorpay order ID for later payment verification
    order.razorpay_order_id = razorpay_order["id"]
    order.save(update_fields=["razorpay_order_id"])

    return JsonResponse({
        "order_number": order.order_number,
        "razorpay_order_id": razorpay_order["id"],
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "amount": razorpay_order["amount"],
        "currency": razorpay_order["currency"],
    })


@login_required
@require_POST
@never_cache
def verify_razorpay_payment_view(request):
    #read  details from checkout frontend
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"message":"Invalid request data"}, status=400)

    order_number = data.get("order_number")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")

    #find order belong to the currently logged in user
    from orders.models import Order

    order = Order.objects.filter(order_number = order_number, user=request.user, payment_method = "Razorpay").first()

    if not order:
        return JsonResponse({"message" : "Order not found"}, status=404)

    #ensure the submitted razorpay order matches the saved order
    if order.razorpay_order_id != razorpay_order_id:
        return JsonResponse({"message":"Payment details do not match"}, status=400)

    #verify the signature before changing payment or stock record
    if not verify_razorpay_payment(razorpay_order_id,razorpay_payment_id,razorpay_signature):
        return JsonResponse({"message": "Payment verification failed."}, status=400)

    #finalize the order only after signature verification success
    order, error = finalize_razorpay_order(order.id, razorpay_payment_id)

    if error:
        return JsonResponse({"message": error}, status=400)

    return JsonResponse({
        "message": "Payment verified successfully.",
        "order_number": order.order_number,
    })


@login_required
@never_cache
def payment_success_view(request):
    order_number = request.GET.get("order_number")
    from orders.models import Order

    order = None
    if order_number:
        order = Order.objects.filter(order_number=order_number, user=request.user).first()

    if not order:
        return redirect("checkout:checkout")

    return render(request, "checkout/payment_success.html", {"order": order})


@login_required
@never_cache
def payment_failure_view(request):
    order_number = request.GET.get("order_number")
    error_message = request.GET.get("error_message") or request.GET.get("message")
    from orders.models import Order

    order = None
    if order_number:
        order = Order.objects.filter(order_number=order_number, user=request.user).first()

    return render(
        request,
        "checkout/payment_failure.html",
        {
            "order": order,
            "error_message": error_message,
        },
    )
