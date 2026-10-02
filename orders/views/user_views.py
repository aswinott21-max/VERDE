import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST

from orders.services.order_service import validate_user_cart_stock



@require_POST
def checkout_api(request):
    stock_valid, error_message = validate_user_cart_stock(request.user)

    if not stock_valid:
        return JsonResponse(
            {
                "status": "error",
                "message": error_message,
            },status=400,)

    try:
        data = json.loads(request.body)

    except json.JSONDecodeError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },status=400,)

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

    for field in required_fields:

        if not data.get(field):
            return JsonResponse(
                {
                    "status": "error",
                    "message": f"{field} is required.",
                },
                status=400,
            )

    return JsonResponse(
        {
            "status": "success",
            "message": "Checkout validation successful.",
        },
        status=200,
    )