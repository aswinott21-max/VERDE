from django.shortcuts import render, redirect
from products.models import Category
from products.services.product_service import (get_active_products,get_product_modal_data,)
from wishlist.services.wishlist_service import (get_user_wishlist_product_ids,get_user_wishlist_count,)

def product_list(request):
    search_query = request.GET.get("search", "")
    category_id = request.GET.get("category", "")
    min_price = request.GET.get("min_price", "")
    max_price = request.GET.get("max_price", "")
    sort_by = request.GET.get("sort", "")
    page = request.GET.get("page", 1)

    result = get_active_products(
        search_query=search_query,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        page=page,
    )

    # category filter options.
    categories = Category.objects.filter(is_active=True)

    # Get wishlist state for the logged-in user.
    if request.user.is_authenticated:
        wishlist_product_ids = get_user_wishlist_product_ids(request.user)
        wishlist_count = get_user_wishlist_count(request.user)
    else:
        wishlist_product_ids = set()
        wishlist_count = 0

    context = {
        "products": result["products"],
        "search_query": search_query,
        "category_id": category_id,
        "min_price": min_price,
        "max_price": max_price,
        "sort_by": sort_by,
        "page": result["page"],
        "total_pages": result["total_pages"],
        "total_products": result["total_products"],
        "has_next": result["has_next"],
        "has_previous": result["has_previous"],
        "categories": categories,
 
        "wishlist_product_ids": wishlist_product_ids,
        "wishlist_count": wishlist_count,
    }

    return render(request,"products/user_product_listing.html",context,)


def product_detail(request, product_id):
    product_data = get_product_modal_data(product_id)

    #redirect unavailable products back to the product listing
    if product_data is None:
        return redirect("product_list")

    if request.user.is_authenticated:
        wishlist_product_ids = get_user_wishlist_product_ids(request.user)
        wishlist_count = get_user_wishlist_count(request.user)
    else:
        wishlist_product_ids = set()
        wishlist_count = 0

    context = {
        "product": product_data["product"],
        "sale_price": product_data["sale_price"],
        "rating_summary": product_data["rating_summary"],
        "reviews": product_data["reviews"],
        "related_products": product_data["related_products"],

        "wishlist_product_ids": wishlist_product_ids,
        "wishlist_count": wishlist_count,
        }

    return render(request,"products/user_product_detail.html",context,)