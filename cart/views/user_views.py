import json

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache

from coupons.models import Coupon,CouponUsage

from coupons.services.coupon_service import (is_coupon_valid,is_coupon_usage_available,is_minimum_order_amount_met,)
from cart.services.cart_service import (add_to_cart,get_cart_details,remove_from_cart,update_cart_quantity,)
from checkout.services.checkout_service import (validate_checkout_coupon,calculate_coupon_eligible_subtotal)

@login_required
@never_cache
def cart_page(request):
    return render(request,"cart/cart.html",)

@login_required
@require_POST
@never_cache
def apply_coupon(request):
    coupon_code = request.POST.get("coupon_code", "").strip()

    if not coupon_code:
        return JsonResponse({"message": "Enter a coupon code."}, status=400)
    cart_data = get_cart_details(request.user)

    #prevent coupon apply for empty cart
    if not cart_data["items"]:
        return JsonResponse({"message": "Your cart is empty."}, status=400)

    eligible_subtotal = calculate_coupon_eligible_subtotal(
        (item["product"], item["item_total"])
        for item in cart_data["items"]
    )

    coupon, discount, error = validate_checkout_coupon(
        coupon_code, eligible_subtotal, request.user
    )

    if error:
        return JsonResponse({"message": error}, status=400)

    #store the selected coupon ID without making it as used
    request.session["checkout_coupon_id"]=coupon.id

    return JsonResponse({
        "message": f"Coupon {coupon.code} applied successfully.",
        "coupon_code": coupon.code,
        "discount_amount": str(discount),
    })

@login_required
@require_POST
@never_cache
def remove_coupon(request):
    request.session.pop("checkout_coupon_id", None)
    return JsonResponse({"message": "Coupon removed successfully."})


@login_required
@require_GET
@never_cache
def available_coupons_api(request):

    cart_data = get_cart_details(request.user)
    subtotal = cart_data["subtotal"]
    eligible_subtotal = calculate_coupon_eligible_subtotal(
        (item["product"], item["item_total"])
        for item in cart_data["items"])

    coupons = Coupon.objects.all().order_by("expiry_date")
    available_coupons =[]

    for coupon in coupons:

        if not is_coupon_valid(coupon):
            continue
        if not is_coupon_usage_available(coupon):
            continue
        if CouponUsage.objects.filter(coupon=coupon, user=request.user).exists():
            continue

        #check cart met minimum coupon amuont
        minimum_met = is_minimum_order_amount_met(coupon, eligible_subtotal)

        available_coupons.append({
            "code": coupon.code,
            "coupon_name": coupon.coupon_name,
            "discount_type": coupon.discount_type,
            "discount_value": str(coupon.discount_value),
            "max_discount_amount": (
                str(coupon.max_discount_amount)
                if coupon.max_discount_amount is not None
                else None),
            "minimum_order_amount": str(coupon.minimum_order_amount),
            "expiry_date": coupon.expiry_date.isoformat(),
            "minimum_met": minimum_met,
            "amount_needed": str(max(coupon.minimum_order_amount - eligible_subtotal, 0)),
        })

    return JsonResponse({
        "status": "success",
        "subtotal": str(subtotal),
        "coupons": available_coupons,
    })






# View the cart for logged-in users
@login_required
@require_GET
def view_cart_api(request):

    cart_data = get_cart_details(request.user)

    serialized_items = []

    #Convert database cart items into API-friendly data
    for item in cart_data["items"]:
        variant = item["variant"]
        primary_image = item["primary_image"]

        serialized_items.append({
            "cart_item_id": item["cart_item_id"],
            "product_id": item["product"].id,
            "product_name": item["product"].name,
            "variant_id": variant.id if variant else None,
            "variant_name": (
                f"{variant.color} / {variant.size}"
                if variant
                else None),

            "quantity": item["quantity"],
            "unit_price": str(item["unit_price"]),
            "item_total": str(item["item_total"]),
            "image_url": (
                primary_image.image_url.url
                if primary_image and primary_image.image_url
                else None),
            })


    return JsonResponse(
        {
            "status": "success",
            "items": serialized_items,
            "subtotal": str(cart_data["subtotal"]),
            "total_items": cart_data["total_items"],
        },status=200,)


# Add a product to the logged-in user's cart
@login_required
@require_POST
def add_to_cart_api(request):

    try:
        data = json.loads(request.body)

        product_id = data.get("product_id")
        variant_id = data.get("variant_id")
        quantity = int(data.get("quantity", 1))

    #handle invalid JSON or invalid quantity data
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },status=400,)

    if not product_id:
        return JsonResponse(
            {
                "status": "error",
                "message": "product_id is required.",
            },status=400,)


    #add the product to the user database cart
    cart_item, error_message = add_to_cart(request.user,product_id,variant_id,quantity,)


    if not cart_item:
        return JsonResponse(
            {
                "status": "error",
                "message": error_message,
            },status=400,)

    # Return successful database-cart response
    return JsonResponse(
        {
            "status": "success",
            "message": "Item added to cart.",
            "cart_item_id": cart_item.id,
        },status=200,)


@login_required
@require_POST
def remove_from_cart_api(request):
# Remove an item from the logged-in user's cart

    try:
        data = json.loads(request.body)


    except json.JSONDecodeError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },status=400,)



    #get the database cart item id
    cart_item_id = data.get("cart_item_id")

    if not cart_item_id:
        return JsonResponse(
            {
                "status": "error",
                "message": "cart_item_id is required.",
            },status=400,)

    #remove the item from the user's database cart
    success = remove_from_cart(request.user,cart_item_id,)


    if not success:
        return JsonResponse(
            {
                "status": "error",
                "message": "Cart item not found.",
            },status=404,)

    return JsonResponse(
        {
            "status": "success",
            "message": "Item removed from cart.",
        },status=200,)

# Update cart quantity for the logged-in user
@login_required
@require_POST
def update_cart_quantity_api(request):

    try:
        data = json.loads(request.body)

        cart_item_id = data.get("cart_item_id")
        quantity = data.get("quantity")


    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },status=400,)

    if quantity is None:
        return JsonResponse(
            {
                "status": "error",
                "message": "quantity is required.",
            },status=400,)


    if not cart_item_id:
        return JsonResponse(
            {
                "status": "error",
                "message": "cart_item_id is required.",
            },status=400,)

    #Update the database cart item
    cart_item, error_message = update_cart_quantity(request.user,cart_item_id,quantity,)

    if not cart_item:
        return JsonResponse(
            {
                "status": "error",
                "message": error_message,
            },status=400,)

    return JsonResponse(
        {
            "status": "success",
            "message": "Cart quantity updated.",
            "cart_item_id": cart_item.id,
            "quantity": cart_item.quantity,
        }, status=200,)
