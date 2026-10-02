import re
from decimal import Decimal, InvalidOperation

def validate_pot_product_data(name, description, category_id, variants):

    name = (name or "").strip()
    description = (description or "").strip()

    if not name:
        return "Product name is required"

    if not re.search(r"[A-Za-z]", name):
        return "Product name must contain letters"

    if not re.fullmatch(r"[A-Za-z0-9 &'\-]+", name):
        return "Product name contains invalid charecters."

    if not description:
        return "Product description is required"

    if not re.search(r"[A-Za-z]", description):
        return "Product description must contain letters."

    if not category_id:
        return "Product category required"

    if not variants:
        return "At least one variant is required"

    seen_combination = set()

    for variant in variants:
        size = variant.get("size", "").strip()
        color = variant.get("color", "").strip()
        price = variant.get("price")
        stock = variant.get("stock")
        low_stock_threshold = variant.get("low_stock_threshold")
        max_purchase_quantity = variant.get("max_purchase_quantity")

        if not all([size,color,price not in (None, ""),stock not in (None, ""),low_stock_threshold not in (None,""),max_purchase_quantity not in (None,"")]):
            return "Size, color, price, stock and low-stock threshold are required."

        try:
            if float(price) <= 0:
                return "Variant price must be greater than 0"
        except(TypeError,ValueError):
            return "Variant price must be a valid number"

        try:
            if int(stock) < 0:
                return "Variant stock cannot be negative"
        except(TypeError,ValueError):
            return "Variant stock must be a valid number"

        try:
            if int(low_stock_threshold) < 0:
                return "Low stock threshold cannot be negative"
        except(TypeError,ValueError):
            return "Low stock threshold must be a valid number"

        try :
            if int(max_purchase_quantity) < 1:
                return "Maximum purchase quantity must be at least 1"
        except(TypeError, ValueError):
            return "maximum purchase quantity must be a valid whole number"

        # Prevent duplicate size and color combinations.
        combination =(size.lower(), color.lower())

        if combination in seen_combination:
            return f"Duplicate variant found: {size}/{color}."

        seen_combination.add(combination)

    return None
 


def validate_pot_images(product_images, variant_images):
    #validate that at least 3 common product images are provided.
    if len(product_images)<3:
        return "At least 3 product images are required."

    # Validate that every variant has exactly one image.
    if not all(image for image in  variant_images):
        return "One image is required for every variant."

    return None