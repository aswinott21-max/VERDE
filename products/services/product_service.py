from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Avg, Count

from products.models import Product, Review
from products.services.product_price_service import get_product_sale_price
from products.services.category_service import get_category_and_subcategory_ids



def get_active_products(search_query=None,category_id=None,min_price=None,max_price=None,sort_by=None,page=1,per_page=12,):

    #Returns active products from active categories.
    #Supports - product name/description search ,pagination

    products = (
        Product.objects.filter(is_active=True,category__is_active=True,).select_related("category").prefetch_related("product_images"))

    if search_query:
        search_query = search_query.strip()

        if search_query:
            products = products.filter(Q(name__icontains=search_query) | Q(description__icontains=search_query))

    if category_id:
        category_ids = get_category_and_subcategory_ids(category_id)

        products = products.filter(category_id__in=category_ids)

    if min_price not in (None, ""):
        products = products.filter(regular_price__gte=min_price)

    if max_price not in (None, ""):
        products = products.filter(regular_price__lte=max_price)

    sort_mapping = {
        "price_low_high": "regular_price",
        "price_high_low": "-regular_price",
        "name_a_z": "name",
        "name_z_a": "-name",
    }

    order_by = sort_mapping.get(sort_by, "-created_at")

    products = products.order_by(order_by)

    paginator = Paginator(products, per_page)

    page_object = paginator.get_page(page)

    return {
        "products": page_object.object_list,
        "page": page_object.number,
        "total_pages": paginator.num_pages,
        "total_products": paginator.count,
        "has_next": page_object.has_next(),
        "has_previous": page_object.has_previous(),
    }



def get_product_details(product_id):

    # Returns an active product with its category,
    # images, active variants, and calculated sale price.

    product = (Product.objects.filter(id=product_id,is_active=True,category__is_active=True,).select_related("category").prefetch_related("product_images","variants","variants__images",).first())

    if product:
        product.sale_price = get_product_sale_price(product)

    return product


def get_product_rating_summary(product_id):
   
    #Returns the average rating and total review count for a product.
   
    summary = Review.objects.filter(
        product_id=product_id
    ).aggregate(
        average_rating=Avg("rating"),
        review_count=Count("id"),
    )

    return {
        "average_rating": summary["average_rating"],
        "review_count": summary["review_count"],
    }


def get_product_reviews(product_id):
   
    #Returns reviews for a product with user,variant, and review-image data.
    
    reviews = (Review.objects.filter(product_id=product_id).select_related("user", "product_variant").prefetch_related("images").order_by("-created_at"))

    return reviews

def get_product_modal_data(product_id):
   
    #Returns all product data required by the product details modal.
    product = get_product_details(product_id)

    if product is None:
        return None

    rating_summary = get_product_rating_summary(product_id)
    reviews = get_product_reviews(product_id)
    related_products = get_related_products(product_id)

    return {
        "product": product,
        "sale_price": product.sale_price,
        "rating_summary": rating_summary,
        "reviews": reviews,
        "related_products" :related_products,
    }

def get_related_products(product_id, limit=4):

    #Returns active products from the same category,excluding the current product.

    product = (
        Product.objects
        .filter(
            id=product_id,
            is_active=True,
            category__is_active=True,
        )
        .select_related("category")
        .first()
    )

    if product is None:
        return Product.objects.none()

    return (Product.objects.filter(category_id=product.category_id,is_active=True,category__is_active=True,)
        .exclude(id=product_id)
        .select_related("category")
        .prefetch_related("product_images")
        .order_by("-created_at")[:limit]
    )
