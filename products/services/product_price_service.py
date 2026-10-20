from decimal import Decimal
from django.utils import timezone


def calculate_discounted_price(regular_price, discount_value):
  
    regular_price = Decimal(regular_price)
    discount_value = Decimal(discount_value)

   
    discount_amount = regular_price * discount_value / Decimal("100")

    
    return (regular_price - discount_amount).quantize(Decimal("0.01"))


def get_effective_discount_percentage(product):
    # Return the highest currently active product or category offer.
    current_time = timezone.now()
    category = product.category

    active_offers = []

    if (
        product.product_offer > 0
        and (product.offer_start_at is None or current_time >= product.offer_start_at)
        and (product.offer_ends_at is None or current_time <= product.offer_ends_at)
    ):
        active_offers.append(product.product_offer)

    if (
        category.discount_value > 0
        and (category.offer_start_at is None or current_time >= category.offer_start_at)
        and (category.offer_end_at is None or current_time <= category.offer_end_at)
    ):
        active_offers.append(category.discount_value)

    return max(active_offers) if active_offers else 0


def get_product_sale_price(product, base_price=None):
    # Calculate the sale price using the highest active offer.
    if base_price is None:
        base_price = product.regular_price

    discount_percentage = get_effective_discount_percentage(product)

    if discount_percentage:
        return calculate_discounted_price(base_price, discount_percentage)

    return base_price