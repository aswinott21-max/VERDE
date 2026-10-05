import logging
import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from users.models import Address

from cart.services.cart_service import get_cart_details
from checkout.services.checkout_service import create_order

# Create your views here.

logger = logging.getLogger(__name__)

@login_required
def checkout_page(request):

    cart_data = get_cart_details(request.user)

    addresses = Address.objects.filter(user=request.user).order_by("-is_default", "-created_at")

    logger.info("Checkout page opened by user: %s with %s cart items",request.user,len(cart_data["items"])),
    return render(request,"checkout/checkout.html", {"cart_data" : cart_data, "addresses" : addresses},)


@login_required
@require_POST
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

    order,error = create_order(
        user=request.user,
        address_id=address_id,
        delivery_method=delivery_method,
        payment_method=payment_method,
    )

    if error:
        return JsonResponse({"message":error},status=400)
    return JsonResponse({"message":"Order placed successfully", "order_number":order.order_number}, status=201)

