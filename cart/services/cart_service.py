from decimal import Decimal

from cart.models import Cart, CartItem
from products.models import Product, ProductVariant
from products.services.product_price_service import get_product_sale_price
from wishlist.services.wishlist_service import remove_from_wishlist

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
    product, variant = _get_product_and_variant(
        product_id,
        product_variant_id,
    )

    # Stop if the product or variant is invalid
    if not product:
        return None

    # Convert quantity to an integer
    quantity = int(quantity)

    # Quantity must be greater than zero
    if quantity <= 0:
        return None

    # Get the available stock for the product or variant
    if variant:
        available_stock = variant.stock_quantity
    else:
        available_stock = product.stock_quantity


    #Get or create the user's active cart
    cart = get_or_create_user_cart(user)

    # Get the current unit price
    unit_price = _get_unit_price(product, variant)

    # Check whether the same product/variant is already in the cart
    cart_item = (CartItem.objects.filter(cart=cart,product=product,product_variant=variant,).first())

    # Calculate the quantity that would be in the cart after adding
    current_quantity = cart_item.quantity if cart_item else 0
    requested_quantity = current_quantity + quantity

    # Do not allow the cart quantity to exceed available stock
    if requested_quantity > available_stock:
        return None

    # If the item already exists, increase its quantity
    if cart_item:
        cart_item.quantity += quantity
        cart_item.unit_price = unit_price
        cart_item.save(update_fields=["quantity", "unit_price", "updated_at"])

    #create a new cart item
    else:
        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            product_variant=variant,
            quantity=quantity,
            unit_price=unit_price,
        )

    # Remove the product/variant from the wishlist,only after the cart addition success
    remove_from_wishlist(
        user,
        product.id,
        variant.id if variant else None,
    )

    return cart_item


# Remove a cart item from a logged-in user's cart
def remove_from_cart(user, cart_item_id):
    cart_item = (
        CartItem.objects.filter(id=cart_item_id,cart__user=user,cart__is_active=True,).first())

    
    if not cart_item:
        return False

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
        .select_related(
            "product",
            "product_variant",
        )
        .prefetch_related(
            "product__product_images",
            "product_variant__images",
        )
    )

    items = []
    subtotal = Decimal("0.00")

    # Process every cart item
    for item in cart_items:
        item_total = item.unit_price * item.quantity
        subtotal += item_total

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
        "total_items": sum(item["quantity"] for item in items),
    }


# Add a product or variant to a guest user's session cart
def add_to_guest_cart(request, product_id, product_variant_id=None, quantity=1):
    product, variant = _get_product_and_variant(product_id,product_variant_id,)

    if not product:
        return None

    # Convert quantity to an integer
    quantity = int(quantity)

    # Quantity must be greater than zero
    if quantity <= 0:
        return None

  
    if variant:
        available_stock = variant.stock_quantity
    else:
        available_stock = product.stock_quantity

    # Create a unique key using product and variant IDs
    key = f"{product.id}:{variant.id if variant else 'none'}"

    
    # Get the current unit price
    unit_price = _get_unit_price(product, variant)

    # Get the guest cart from the session
    cart = request.session.get("guest_cart", {})

    # Create a unique key using product and variant IDs
    key = f"{product.id}:{variant.id if variant else 'none'}"
    
    current_quantity = cart[key]["quantity"] if key in cart else 0
    request_quantity = current_quantity + quantity
    
    
    if request_quantity > available_stock:
            return None
    

    # If the item already exists, increase its quantity
    if key in cart:
        cart[key]["quantity"] += quantity
        cart[key]["unit_price"] = str(unit_price)

    # Otherwise create a new guest cart item
    else:
        cart[key] = {
            "product_id": product.id,
            "variant_id": variant.id if variant else None,
            "quantity": quantity,
            "unit_price": str(unit_price),
        }

    # Save the updated cart in the session
    request.session["guest_cart"] = cart
    request.session.modified = True

    return cart[key]


# Get all cart details for a guest user
def get_guest_cart(request):
    
    cart = request.session.get("guest_cart", {})

    items = []
    subtotal = Decimal("0.00")

    # Process every guest cart item
    for item in cart.values():
        product, variant = _get_product_and_variant(
            item["product_id"],
            item["variant_id"],
        )

        if not product:
            continue

        quantity = int(item["quantity"])
        unit_price = Decimal(item["unit_price"])
        item_total = unit_price * quantity

        subtotal += item_total

        items.append({
            "product": product,
            "variant": variant,
            "quantity": quantity,
            "unit_price": unit_price,
            "item_total": item_total,
        })

    return {
        "items": items,
        "subtotal": subtotal,
        "total_items": sum(item["quantity"] for item in items),
    }


# Remove an item from a guest user's session cart
def remove_from_guest_cart(request, product_id, product_variant_id=None):
   
    cart = request.session.get("guest_cart", {})

    # Create the same key used when adding the item
    key = f"{product_id}:{product_variant_id if product_variant_id else 'none'}"

    # Check whether the item exists
    if key not in cart:
        return False

    del cart[key]

    #Save
    request.session["guest_cart"] = cart
    request.session.modified = True

    return True


# Update the quantity of an item in the guest cart
def update_guest_cart_quantity(request,product_id,product_variant_id=None,quantity=1,):

    cart = request.session.get("guest_cart", {})

    
    key = f"{product_id}:{product_variant_id if product_variant_id else 'none'}"

    # Check whether the item exists in the guest cart
    if key not in cart:
        return None, "Cart item not found."

    # Convert quantity to an integer
    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        return None, "Invalid quantity."

    # Quantity must be at least one
    if quantity <= 0:
        return None, "Quantity must be at least 1."

    # Get the current product and variant
    product, variant = _get_product_and_variant(
        product_id,
        product_variant_id,
    )

    # Product or variant is no longer available
    if not product:
        return None, "Invalid product or variant."

    # Check stock based on whether the product has a variant
    if variant:
        available_stock = variant.stock_quantity
    else:
        available_stock = product.stock_quantity

    # Prevent the requested quantity from exceeding available stock
    if quantity > available_stock:
        return None, "Requested quantity exceeds available stock."

    # Update the quantity in the guest cart
    cart[key]["quantity"] = quantity

    # Save the updated cart back to the session
    request.session["guest_cart"] = cart
    request.session.modified = True

    return cart[key], None


# Merge the guest cart into the user's database cart after login
def merge_guest_cart_to_user_cart(request, user):
    # Get the guest cart from the session
    guest_cart = request.session.get("guest_cart", {})

    # Nothing to merge
    if not guest_cart:
        return

    # Add every guest cart item to the user's database cart
    for item in guest_cart.values():
        add_to_cart(user=user,product_id=item["product_id"],product_variant_id=item["variant_id"],quantity=item["quantity"],)

    # Remove the guest cart after merging
    del request.session["guest_cart"]
    request.session.modified = True
    request.session.save()


# Update the quantity of an item in a logged-in user's cart
def update_cart_quantity(user, cart_item_id, quantity):
    # Find the cart item belonging to the logged-in user
    cart_item = (CartItem.objects.filter(id=cart_item_id,cart__user=user,cart__is_active=True,).select_related("product","product_variant",).first())

    # Cart item was not found
    if not cart_item:
        return None, "Cart item not found."

    # Convert quantity to an integer
    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        return None, "Invalid quantity."

    # Quantity must be at least one
    if quantity <= 0:
        return None, "Quantity must be at least 1."

    # Check stock based on whether the product has a variant
    if cart_item.product_variant:
        available_stock = cart_item.product_variant.stock_quantity
    else:
        available_stock = cart_item.product.stock_quantity

    # Prevent the requested quantity from exceeding available stock
    if quantity > available_stock:
        return None, "Requested quantity exceeds available stock."

    # Update the database cart item quantity
    cart_item.quantity = quantity
    cart_item.save(update_fields=["quantity", "updated_at"])

    return cart_item, None
