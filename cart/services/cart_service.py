from decimal import Decimal
from django.db import transaction
from cart.models import Cart, CartItem
from products.models import Product, ProductVariant
from products.services.product_price_service import get_product_sale_price
from wishlist.services.wishlist_service import remove_from_wishlist
from products.services.tax_service import calculate_tax

# Get or create an active cart for a logged-in user
def get_or_create_user_cart(user):
    cart, created = Cart.objects.get_or_create(user=user,is_active=True,)
    return cart


# Get an active product and its optional active variant
def _get_product_and_variant(product_id, product_variant_id=None):
    product = (
        Product.objects
        .filter(id=product_id,is_active=True,category__is_active=True,).select_related("category").first())

    # Product does not exist or is inactive
    if not product:
        return None, None

    variant = None

    # Get the variant only when a variant ID is provided
    if product_variant_id:
        variant = (ProductVariant.objects.filter(id=product_variant_id,product=product,is_active=True,).first())

        # Variant does not exist, belongs to another product, or is inactive
        if not variant:
            return None, None

    return product, variant


# Get the current selling price for a product or variant
def _get_unit_price(product, variant=None):
    # Pot variants use their own price
    if variant:
        return Decimal(variant.price)

    # Normal products use the product sale price
    return Decimal(get_product_sale_price(product))


# Add a product or variant to a logged-in user's cart
def add_to_cart(user, product_id, product_variant_id=None, quantity=1):
    with transaction.atomic():

        product, variant = _get_product_and_variant(product_id,product_variant_id,)
        #Stop if the product or variant is invalid
        if not product:
            return None, "Invalid product or variant."

        # Convert quantity to an integer
        quantity = int(quantity)

        # Quantity must be greater than zero
        if quantity <= 0:
            return None, "Invalid quantity"

        # Get the available stock and maximum purchase limit
        if variant:
            available_stock = variant.stock_quantity
            max_purchase_quantity = variant.max_purchase_quantity
        else:
            available_stock = product.stock_quantity
            max_purchase_quantity = product.max_purchase_quantity

        # Product has no stock
        if available_stock <= 0:
            return None, "Product is out of stock"

        # Get or create the user's active cart
        cart = get_or_create_user_cart(user)

        # Check whether the same product/variant is already in the cart
        cart_item = (
            CartItem.objects.filter(cart=cart,product=product, product_variant=variant,).first())

        #Get the current quantity already reserved in the cart
        current_quantity = cart_item.quantity if cart_item else 0

        #calculate the new total cart quantity
        requested_quantity = current_quantity + quantity

        #check the maximum purchase limit
        if requested_quantity > max_purchase_quantity:
            return None, "Requested quantity exceeds the maximum allowed quantity"

        #check whether enough currently available stock exists
        if quantity > available_stock:
            return None, "Requested quantity exceeds available stock"

        #get the current unit price
        unit_price = _get_unit_price(product, variant)


        # If the item already exists, increase its quantity
        if cart_item:
            cart_item.quantity += quantity
            cart_item.unit_price = unit_price
            cart_item.save(
                update_fields=[
                    "quantity",
                    "unit_price",
                    "updated_at",
                ]
            )

        # Otherwise create a new cart item
        else:
            cart_item = CartItem.objects.create(
                cart=cart,
                product=product,
                product_variant=variant,
                quantity=quantity,
                unit_price=unit_price,
            )

        # Remove the product/variant from the wishlist only
        # after the cart addition succeeds
        remove_from_wishlist(user,product.id,variant.id if variant else None,)
        return cart_item, None


# Remove a cart item from a logged-in user's cart
def remove_from_cart(user, cart_item_id):
    with transaction.atomic():

        #Find the cart item belonging to the user's active cart
        cart_item =(CartItem.objects.filter(id=cart_item_id,cart__user=user,cart__is_active=True,).first())
        
        
        if not cart_item:
            return False

        #Remove from cart
        cart_item.delete()

        return True



# Get all cart details for a logged-in user
def get_cart_details(user):
    cart = (Cart.objects.filter(user=user,is_active=True,).first())

    # Return an empty cart when the user has no active cart
    if not cart:
        return {
            "items": [],
            "subtotal": Decimal("0.00"),
            "total_items": 0,
        }

    # Get cart items together with related product and image data
    cart_items = (
        CartItem.objects
        .filter(cart=cart)
        .select_related("product","product_variant","product__category",).prefetch_related("product__product_images","product_variant__images",))

    items = []
    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")

    # Process every cart item
    for item in cart_items:
        item_total = item.unit_price * item.quantity
        subtotal += item_total
        tax_amount += calculate_tax(item.product, item_total)

        primary_image = None

        # For variants, try to use the variant's primary image first
        if item.product_variant:
            primary_image = (
                item.product_variant.images
                .filter(is_primary=True)
                .first()
                or item.product_variant.images.first()
            )

        # If no variant image exists, use the product image
        if not primary_image:
            primary_image = (
                item.product.product_images
                .filter(is_primary=True)
                .first()
                or item.product.product_images.first()
            )

        items.append({
            "cart_item_id": item.id,
            "product": item.product,
            "variant": item.product_variant,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "item_total": item_total,
            "primary_image": primary_image,
        })

    return {
        "items": items,
        "subtotal": subtotal,
        "tax_amount": tax_amount,
        "total_items": sum(item["quantity"] for item in items),
    }


# Update the quantity of an item in a logged-in user's cart
def update_cart_quantity(user, cart_item_id, quantity):
    with transaction.atomic():

        # Find the cart item belonging to the logged-in user
        cart_item = (CartItem.objects.filter(id=cart_item_id,cart__user=user,cart__is_active=True,)
            .select_related("product", "product_variant").first())

        if not cart_item:
            return None, "Cart item not found."

        #convert qty to integer
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            return None, "Invalid quantity."

        
        if quantity <= 0:
            return None, "Quantity must be at least 1."

        # Get the current quantity already reserved in the cart
        current_quantity = cart_item.quantity

        # Get stock and maximum purchase quantity
        if cart_item.product_variant:
            stock_object = cart_item.product_variant
            available_stock = stock_object.stock_quantity
            max_purchase_quantity = stock_object.max_purchase_quantity
        else:
            stock_object = cart_item.product
            available_stock = stock_object.stock_quantity
            max_purchase_quantity = stock_object.max_purchase_quantity

        # Customer cannot exceed the admin purchase limit
        if quantity > max_purchase_quantity:
            return None, "Requested quantity exceeds allowed quantity."

        #calculate how much the reserved quantity is changing
        quantity_difference = quantity - current_quantity

        #customer is increasing the cart quantity
        if quantity_difference > 0:

            if quantity_difference > available_stock:
                return None, "Requested quantity exceeds allowed quantity."

        #update
        cart_item.quantity = quantity
        cart_item.save(update_fields=["quantity", "updated_at"])

        return cart_item, None