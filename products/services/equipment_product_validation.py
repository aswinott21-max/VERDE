def validate_equipment_product_data(name, description, category_id, regular_price, stock_quantity,low_stock_threshold):
    if not all([name and name.strip(), description and description.strip(), category_id, regular_price not in (None,""),stock_quantity not in(None, ""),low_stock_threshold not in(None,"")]):
        return "All equipment product fields are required"

    try:
        if float(regular_price) <= 0:
            return "Regular price must be greater than 0."
    except(TypeError,ValueError):
        return "Regular price must be a valid number."

    try:
        if int(stock_quantity) < 0:
            return "Quantity cannot be negative."
    except (TypeError,ValueError):
        return "Quantity must be a valid number."

    try:
        if int(low_stock_threshold)<0:
            return "Low-stock threshold cannot be negative"
    except(TypeError,ValueError):
        return "Low stock threshold must be a valid number."

    return None

def validate_equipment_images(product_images):
    if len(product_images) <3:
        return "At least 3 product images are required"

    return None
