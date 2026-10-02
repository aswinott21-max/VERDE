from decimal import Decimal
from django.utils import timezone


def calculate_discounted_price(regular_price, discount_value):
  
    regular_price = Decimal(regular_price)
    discount_value = Decimal(discount_value)

   
    discount_amount = regular_price * discount_value / Decimal("100")

    
    return (regular_price - discount_amount).quantize(Decimal("0.01"))


def get_product_sale_price(product,base_price=None):

    current_time = timezone.now()

    #Use the variant price when provided; otherwise use the product price.
    if base_price is None: 
        base_price = product.regular_price

    # Check whether the product has an active product-level offer.
    if (
        product.product_offer > 0
        and (product.offer_start_at is None or current_time >= product.offer_start_at)
        and (product.offer_ends_at is None or current_time <= product.offer_ends_at)):

        return calculate_discounted_price(base_price,product.product_offer)

   
    category = product.category

    if (
        category.discount_value > 0
        and (
            category.offer_start_at is None
            or current_time >= category.offer_start_at
        )
        and (
            category.offer_end_at is None
            or current_time <= category.offer_end_at
        )
    ):
        
        return calculate_discounted_price(base_price,category.discount_value)

   
    return base_price