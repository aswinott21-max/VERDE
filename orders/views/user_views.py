import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from orders.services.order_service import (validate_user_cart_stock,validate_guest_cart_stock,)



@require_POST
def checkout_api(request):

    # Check the latest stock for a logged-in user's database cart.
    if request.user.is_authenticated:
        stock_valid, error_message = validate_user_cart_stock(request.user)

    # Check the latest stock for a guest user's session cart.
    else:
        stock_valid, error_message = validate_guest_cart_stock(request)

    # Stop checkout when the cart is empty or stock is no longer available.
    if not stock_valid:
        return JsonResponse(
            {
                "status": "error",
                "message": error_message,
            },status=400,)

    try:
        data = json.loads(request.body)

    # Handle invalid JSON.
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },
            status=400,
        )

    # These fields will be required to continue checkout.
    required_fields = [
        "full_name",
        "phone",
        "address_line1",
        "city",
        "state",
        "country",
        "pin",
        "delivery_method",
        "payment_method",
    ]

    # Check that every required checkout field was supplied.
    for field in required_fields:

        # Stop when a required field is missing or empty.
        if not data.get(field):
            return JsonResponse(
                {
                    "status": "error",
                    "message": f"{field} is required.",
                },
                status=400,
            )

    # Return the validated checkout information for now.
    # Order creation will be added in the next step.
    return JsonResponse(
        {
            "status": "success",
            "message": "Checkout validation successful.",
        },
        status=200,
    )