from decimal import Decimal, InvalidOperation

def validate_pot_product_data(name, description, category_id, variants):

    if not all([name and name.strip(), description and description.strip(), category_id]):
        return "Product name, description and category are required."

    if not variants:
        return "At least one product variant is required."

    seen_combinations = set()

    for variant in variants:
        size = variant.get("size", "").strip()
        color = variant.get("color", "").strip()
        price = variant.get("price")
        stock = variant.get("stock")
        low_stock_threshold = variant.get("low_stock_threshold")

        if not all([size,color,price not in(None, ""),stock not in (None,""), low_stock_threshold not in (None,"")]):
            return "Size, color, price, stock and low-stock threshold are required"

        try:
            if float(price)<=0:
                return "Variant price must be greater than 0."
        except (TypeError, ValueError):
            return "Variant price must be a valid number."

        try:
            if int(stock)<0:
                return "Variant stock cannot be negative"

        except (TypeError,ValueError):
            return "Variant stock must be a valid number"

        try:
            if int(low_stock_threshold) < 0:
                return "Low-stock threshold cannot be negative." 
        except (TypeError, ValueError):
            return "Low-stock threshold must be a valid number."

        #prevent duplicate size and color combinations within the same product.
        combination = (size.lower(), color.lower())

        if combination in seen_combinations:
            return f"Duplicate variant found: {size}/{color}."
        
        seen_combinations.add(combination)
    return None

def validate_pot_images(product_images, variant_images):
    #validate that at least 3 common product images are provided.
    if len(product_images)<3:
        return "At least 3 product images are required."

    # Validate that every variant has exactly one image.
    if not all(image for image in  variant_images):
        return "One image is required for every variant."

    return None