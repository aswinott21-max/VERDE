import re


def validate_equipment_product_data(name,description,category_id,regular_price,stock_quantity,low_stock_threshold,max_purchase_quantity):
    
    name = (name or "").strip()
    description = (description or "").strip()

    if not name:
        return "Product name is required."

    if not re.search(r"[A-Za-z]", name):
        return "Product name must contain letters."

    if not re.fullmatch(r"[A-Za-z0-9 &'\-]+", name):
        return "Product name contains invalid characters."

    if not description:
        return "Product description is required."

    if not re.search(r"[A-Za-z]", description):
        return "Product description must contain letters."

    if not category_id:
        return "Product category is required."

    if regular_price in (None, ""):
        return "Regular price is required."

    try:
        if float(regular_price) <= 0:
            return "Regular price must be greater than 0."
    except (TypeError, ValueError):
        return "Regular price must be a valid number."

    if stock_quantity in (None, ""):
        return "Quantity is required."

    try:
        if int(stock_quantity) < 0:
            return "Quantity cannot be negative."
    except (TypeError, ValueError):
        return "Quantity must be a valid number."

    if low_stock_threshold in (None, ""):
        return "Low-stock threshold is required."

    try:
        if int(low_stock_threshold) < 0:
            return "Low stock threshold cannot be negative."
    except (TypeError, ValueError):
        return "Low-stock threshold must be a valid number."

    if max_purchase_quantity in (None,""):
        return "Maximum purchase quantity is required"
    try:
        if int(max_purchase_quantity) < 1:
            return "Maximum purchase quantity must be at least 1."
    except (TypeError, ValueError):
        return "Maximum purchase quantity must be a valid whole number."
    

    return None


def validate_equipment_images(product_images):
    # At least 3 equipment product images are required.
    if len(product_images) < 3:
        return "At least 3 product images are required."

    return None