from decimal import Decimal
from django.utils import timezone


def calculate_discounted_price(regular_price, discount_value):
    # Convert both values to Decimal for accurate money calculations.
    regular_price = Decimal(regular_price)
    discount_value = Decimal(discount_value)

    # Calculate the discount amount.
    discount_amount = regular_price * discount_value / Decimal("100")

    # Return the final discounted price.
    return (regular_price - discount_amount).quantize(Decimal("0.01"))


def get_product_sale_price(product):

    current_time = timezone.now()

    # Check whether the product has an active product-level offer.
    if (
        product.product_offer > 0
        and (product.offer_start_at is None or current_time >= product.offer_start_at)
        and (product.offer_ends_at is None or current_time <= product.offer_ends_at)):

        # Calculate the sale price using the product-level discount.
        return calculate_discounted_price(product.regular_price,product.product_offer)

    #Get the product's category.
    category = product.category

    #Check whether the category has an active offer.
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
        #calculate the sale price using the category-level discount.
        return calculate_discounted_price(product.regular_price,category.discount_value)

    # Return the regular price when no active offer exists.
    return product.regular_price