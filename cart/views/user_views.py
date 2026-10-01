import json

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from cart.services.cart_service import (add_to_cart,get_cart_details,remove_from_cart,update_cart_quantity,add_to_guest_cart,get_guest_cart,remove_from_guest_cart,update_guest_cart_quantity,)

# Convert guest cart data into API-friendly JSON data
def _serialize_guest_cart(cart_data):
    serialized_items = []

    # Convert each guest cart item into a JSON-friendly format
    for index, item in enumerate(cart_data["items"], start=1):
        variant = item["variant"]

        serialized_items.append({
            "cart_item_id": None,
            "guest_item_id": index,
            "product_id": item["product"].id,
            "product_name": item["product"].name,
            "variant_id": variant.id if variant else None,
            "variant_name": (
                f"{variant.color} / {variant.size}"
                if variant
                else None
            ),
            "quantity": item["quantity"],
            "unit_price": str(item["unit_price"]),
            "item_total": str(item["item_total"]),
        })

    return serialized_items




def cart_page(request):
    return render(request,"cart/cart.html",)



# View the cart for both guest and logged-in users
@require_GET
def view_cart_api(request):

    # Logged-in users use the database cart
    if request.user.is_authenticated:
        cart_data = get_cart_details(request.user)

        serialized_items = []

        # Convert database cart items into API-friendly data
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
                    else None
                ),
                "quantity": item["quantity"],
                "unit_price": str(item["unit_price"]),
                "item_total": str(item["item_total"]),
                "image_url": (
                    primary_image.image_url.url
                    if primary_image and primary_image.image_url
                    else None
                ),
            })

    # Guest users use the session cart
    else:
        cart_data = get_guest_cart(request)
        serialized_items = _serialize_guest_cart(cart_data)

   
    return JsonResponse(
        {
            "status": "success",
            "items": serialized_items,
            "subtotal": str(cart_data["subtotal"]),
            "total_items": cart_data["total_items"],
        },
        status=200,
    )


# Add a product to either the guest or logged-in cart
@require_POST
def add_to_cart_api(request):

    # Read the JSON request data
    try:
        data = json.loads(request.body)

        product_id = data.get("product_id")
        variant_id = data.get("variant_id")
        quantity = int(data.get("quantity", 1))

    # Handle invalid JSON or invalid quantity data
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },
            status=400,
        )

    # Product ID is required
    if not product_id:
        return JsonResponse(
            {
                "status": "error",
                "message": "product_id is required.",
            },
            status=400,
        )

    # Logged-in user → save item in database cart
    if request.user.is_authenticated:

        # Add the product to the user's database cart
        cart_item = add_to_cart(
            request.user,
            product_id,
            variant_id,
            quantity,
        )

        # Product or variant is invalid
        if not cart_item:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Invalid product or variant.",
                },
                status=400,
            )

        # Return successful database-cart response
        return JsonResponse(
            {
                "status": "success",
                "message": "Item added to cart.",
                "cart_item_id": cart_item.id,
            },
            status=200,
        )

    # Guest user → save item in session cart
    guest_item = add_to_guest_cart(
        request,
        product_id,
        variant_id,
        quantity,
    )

    # Product or variant is invalid
    if not guest_item:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid product or variant.",
            },
            status=400,
        )

    # Return successful guest-cart response
    return JsonResponse(
        {
            "status": "success",
            "message": "Item added to guest cart.",
        },
        status=200,
    )


@require_POST
def remove_from_cart_api(request):
# Remove an item from either the guest or logged-in cart
    
    # Read the JSON request data
    try:
        data = json.loads(request.body)

    # Handle invalid JSON
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },
            status=400,
        )

    # Logged-in user → remove using database cart item ID
    if request.user.is_authenticated:

        # Get the database cart item ID
        cart_item_id = data.get("cart_item_id")

        # Cart item ID is required
        if not cart_item_id:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "cart_item_id is required.",
                },
                status=400,
            )

        # Remove the item from the user's database cart
        success = remove_from_cart(
            request.user,
            cart_item_id,
        )

    # Guest user → remove using product and variant IDs
    else:

        # Get product and variant IDs from the request
        product_id = data.get("product_id")
        variant_id = data.get("variant_id")

        # Product ID is required
        if not product_id:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "product_id is required.",
                },
                status=400,
            )

        # Remove the item from the guest session cart
        success = remove_from_guest_cart(
            request,
            product_id,
            variant_id,
        )

    # Item was not found in the cart
    if not success:
        return JsonResponse(
            {
                "status": "error",
                "message": "Cart item not found.",
            },
            status=404,
        )

    # Return successful removal response
    return JsonResponse(
        {
            "status": "success",
            "message": "Item removed from cart.",
        },
        status=200,
    )

# Update cart quantity for logged-in or guest users
@require_POST
def update_cart_quantity_api(request):

    # Read the JSON request data
    try:
        data = json.loads(request.body)

        cart_item_id = data.get("cart_item_id")
        product_id = data.get("product_id")
        variant_id = data.get("variant_id")
        quantity = data.get("quantity")

    # Handle invalid JSON
    except (json.JSONDecodeError, ValueError, TypeError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },
            status=400,
        )

    # Quantity is required
    if quantity is None:
        return JsonResponse(
            {
                "status": "error",
                "message": "quantity is required.",
            },
            status=400,
        )

    # Logged-in user, update database cart
    if request.user.is_authenticated:

        # Database cart requires cart item ID
        if not cart_item_id:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "cart_item_id is required.",
                },
                status=400,
            )

        # Update the database cart item
        cart_item, error_message = update_cart_quantity(
            request.user,
            cart_item_id,
            quantity,
        )

        # Return the update error
        if not cart_item:
            return JsonResponse(
                {
                    "status": "error",
                    "message": error_message,
                },
                status=400,
            )

        # Return successful database-cart response
        return JsonResponse(
            {
                "status": "success",
                "message": "Cart quantity updated.",
                "cart_item_id": cart_item.id,
                "quantity": cart_item.quantity,
            },
            status=200,
        )

    # Guest user → update session cart
    if not product_id:
        return JsonResponse(
            {
                "status": "error",
                "message": "product_id is required.",
            },
            status=400,
        )

    # Update the guest cart item
    guest_item, error_message = update_guest_cart_quantity(
        request,
        product_id,
        variant_id,
        quantity,
    )

    # Return the update error
    if not guest_item:
        return JsonResponse(
            {
                "status": "error",
                "message": error_message,
            },
            status=400,
        )

    # Return successful guest-cart response
    return JsonResponse(
        {
            "status": "success",
            "message": "Cart quantity updated.",
            "product_id": guest_item["product_id"],
            "variant_id": guest_item["variant_id"],
            "quantity": guest_item["quantity"],
        },
        status=200,
    )