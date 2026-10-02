from cart.models import Cart, CartItem

# Check whether all items in a logged-in user's cart,are still available at the latest stock level.

def validate_user_cart_stock(user):

    # Get the user's active cart.
    cart = (Cart.objects.filter(user=user,is_active=True).first())

    # An empty cart cannot be checked out.
    if not cart:
        return False, "Your cart is empty."

    # Get the cart items together with its current product and variant records from the database.
    cart_items = (CartItem.objects.filter(cart=cart).select_related("product","product_variant",))

    # Make sure the cart actually contains items.
    if not cart_items.exists():
        return False, "You cart is empty."

    # Check every cart item against the latest stock.
    for item in cart_items:

        if item.product_variant:
            variant = item.product_variant

            # The variant must still be active.
            if not variant.is_active:
                return False,(
                    f"{item.product.name} - "
                    f"{variant.color} / {variant.size} "
                    "is no longer available."
                )

            # Compare requested quantity with current variant stock.
            if item.quantity > variant.stock_quantity:
                return False, (
                    f"{item.product.name} - "
                    f"{variant.color} / {variant.size} "
                    "does not have enough stock."
                )
        # Products without variants use product-level stock.
        else:
            product = item.product
            # The product must still be active.
            if not product.is_active:
                return False, (f"{product.name} is no longer available.")

            if item.quantity > product.stock_quantity:
                return False, (f"{product.name} does not have enough stock.")
        
    return True, None

