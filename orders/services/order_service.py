from cart.models import Cart, CartItem
from products.models import Product, ProductVariant

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


# Check whether all items in a guest user's session cart,are still available in latest stock level.
def validate_guest_cart_stock(request):
    guest_cart = request.session.get("guest_cart", {})

    if not guest_cart:
        return False, "Your cart is empty."

    # Check every guest cart item against the latest database stock.
    for item in guest_cart.values():

        product_id = item.get("product_id")
        variant_id = item.get("variant_id")
        quantity = item.get("quantity")

        # Find the current active product.
        product = (Product.objects.filter(id=product_id,is_active=True,category__is_active=True,).select_related("category").first())

        # The product no longer exists or is inactive.
        if not product:
            return False, "A product in your cart is no longer available."

        # Guest cart item with a variant.
        if variant_id:

            variant = (ProductVariant.objects.filter(id=variant_id,product=product,is_active=True,).first())
            # The variant no longer exists or is inactive.
            if not variant:
                return False, (
                    f"{product.name} has a selected variant "
                    "that is no longer available."
                )

            # Compare guest cart quantity with latest variant stock.
            if int(quantity) > variant.stock_quantity:
                return False, (
                    f"{product.name} does not have enough stock "
                    "for the selected variant."
                )

        # Guest cart item without a variant.
        else:

            # Compare guest cart quantity with latest product stock.
            if int(quantity) > product.stock_quantity:
                return False, (
                    f"{product.name} does not have enough stock."
                )
    return True, None
