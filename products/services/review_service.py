from django.db import transaction
from django.core.files.storage import default_storage
import re

from orders.models import OrderItem
from products.models import Review,ReviewImage

def get_reviewable_order_items(user, order_number):

    return (
        OrderItem.objects
        .select_related("order", "product", "product_variant")
        .filter(
            order__order_number=order_number,
            order__user=user,
            order__status="DELIVERED",
        )
        .exclude(item_status="CANCELLED")
        .exclude(returns__isnull=False)
        .exclude(
            id__in=Review.objects.filter(user=user)
            .values_list("order_item_id", flat=True)
        )
        .distinct()
    )

@transaction.atomic
def create_product_review(user,order_item_id,rating,review_text="",images=None):
    #review only after delivered
    order_item = (
        OrderItem.objects
        .select_related("order", "product", "product_variant")
        .filter(id=order_item_id,order__user=user,order__status="DELIVERED",).exclude(item_status="CANCELLED").first())
    if not order_item:
        return None,"This product is not eligible for review"

    if order_item.returns.exists():
        return None,"Returned product cannot be reviewed"
    if Review.objects.filter(order_item_id =order_item.id, user=user).exists():
        return None, "You have already reviewed this product"

    if review_text:
        if not re.search(r"[A-Za-z]", review_text):
            return None, "Please enter a valid review"
    review = Review.objects.create(
        order_item_id =order_item.id,
        product = order_item.product,
        product_variant = order_item.product_variant,
        user=user,
        rating=rating,
        review_text=review_text,)
    
    if images:
        for image in images:
            image_path = default_storage.save(f"review_images/{image.name}",image)
            ReviewImage.objects.create(review=review,image_url=default_storage.url(image_path),)

    return review, None