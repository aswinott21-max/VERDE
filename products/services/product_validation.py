def validate_product_data(name, regular_price):

    if not name or not name.strip():
        return "Product name is required."

    if regular_price is None or regular_price == "":
        return "Regular price is required."

    return None