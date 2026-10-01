import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from wishlist.services.wishlist_service import (add_to_wishlist,remove_from_wishlist,get_user_wishlist_items,)


@login_required
def add_to_wishlist_api(request):

    #Only POST allowed
    if request.method != "POST":
        return JsonResponse(
            {
                "status": "error",
                "message": "POST request required.",
            },status=405,)

    #read the JSON request data.
    try:
        data = json.loads(request.body)

        product_id = data.get("product_id")
        variant_id = data.get("variant_id")

    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },status=400,)

    #product ID is required.
    if not product_id:
        return JsonResponse(
            {
                "status": "error",
                "message": "product_id is required.",
            },status=400,)

    #add the product to the user's wishlist.
    item = add_to_wishlist(request.user,product_id,variant_id,)

    return JsonResponse(
        {
            "status": "success",
            "message": "Item added to wishlist.",
            "wishlist_item_id": item.id,
        },status=200,)


@login_required
def wishlist_page(request):

    wishlist_items = get_user_wishlist_items(request.user)

    return render(request,"wishlist/wishlist.html",{
            "wishlist_items": wishlist_items,
        },
    )



@login_required
def remove_from_wishlist_api(request):

    # Only POST requests are allowed.
    if request.method != "POST":
        return JsonResponse(
            {
                "status": "error",
                "message": "POST request required.",
            },
            status=405,
        )

    # Read the JSON request data.
    try:
        data = json.loads(request.body)

        product_id = data.get("product_id")
        variant_id = data.get("variant_id")

    except (json.JSONDecodeError, TypeError):
        return JsonResponse(
            {
                "status": "error",
                "message": "Invalid JSON payload.",
            },
            status=400,
        )

    # Product ID is required.
    if not product_id:
        return JsonResponse(
            {
                "status": "error",
                "message": "product_id is required.",
            },
            status=400,
        )

    success = remove_from_wishlist(request.user,product_id,variant_id,)

    if not success:
        return JsonResponse(
            {
                "status": "error",
                "message": "Wishlist item not found.",
            },
            status=404,
        )

    return JsonResponse(
        {
            "status": "success",
            "message": "Item removed from wishlist.",
        },
        status=200,
    )