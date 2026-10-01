def validate_plant_product_data(name,description,category_id,regular_price,stock_quantity,low_stock_threshold):
    # Validate required product fields.
    if not all([name and name.strip(), description and description.strip(),category_id,regular_price not in (None, ""), stock_quantity not in (None, ""),low_stock_threshold not in (None,"")]):
        return "All plant product field are required."

    # Validate regular price.
    try: 
        if float(stock_quantity)< 0:
            return "Quantity cannot be negative."
    except(TypeError,ValueError):
        return "Quantity must be valid number."

    #low-stock threshold
    try:
        if float(low_stock_threshold)<0:
            return "Low-stock threshold cannot be negative."
    except (TypeError,ValueError):
        return "Low-stock threshold must be a valid number."

    return None
