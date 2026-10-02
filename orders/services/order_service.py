from cart.models import Cart, CartItem

# Check whether all items in a logged-in user's cart,are still available at the latest stock level.

def validate_user_cart_stock(user):

    cart = (Cart.objects.filter(user=user,is_active=True).first())

    if not cart:
        return False, "Your cart is empty."

    # Get the cart items together with its current product and variant records from the database.
    cart_items = (CartItem.objects.filter(cart=cart).select_related("product","product_variant",))

    if not cart_items.exists():
        return False, "You cart is empty."

    #heck every cart item to the latest stock.
    for item in cart_items:

        if item.product_variant:
            variant = item.product_variant

           
            if not variant.is_active:
                return False,(
                    f"{item.product.name} - "
                    f"{variant.color} / {variant.size} "
                    "is no longer available.")

    
            if item.quantity > variant.stock_quantity:
                return False, (
                    f"{item.product.name} - "
                    f"{variant.color} / {variant.size} "
                    "does not have enough stock.")
            
        #products without variants use product level stock.
        else:
            product = item.product
            
            if not product.is_active:
                return False, (f"{product.name} is no longer available.")

            if item.quantity > product.stock_quantity:
                return False, (f"{product.name} does not have enough stock.")
        
    return True, None

