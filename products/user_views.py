from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from products.models import Category

from products.services.product_service import (get_active_products,get_product_modal_data,)
from wishlist.services.wishlist_service import (get_user_wishlist_product_ids,get_user_wishlist_count,)
from products.services.review_service import (get_reviewable_order_items, create_product_review)

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

@login_required
def add_product_review(request, order_number):

    reviewable_items = get_reviewable_order_items(request.user,order_number)

    if request.method == "POST":
        order_item_id = request.POST.get("order_item_id")
        rating = request.POST.get("rating")
        review_text = request.POST.get("review_text","").strip()

        review, error = create_product_review(request.user, order_item_id, rating, review_text, request.FILES.getlist("images"),)

        if error:
            return render(request,"products/add_product_review.html",
                          {
                            "reviewable_items": reviewable_items,
                            "order_number": order_number,
                            "error": error,
                          })
        return redirect("orders:order_detail", order_number=order_number)
    return render(request,"products/add_product_review.html",{"reviewable_items": reviewable_items,"order_number": order_number,},)
   