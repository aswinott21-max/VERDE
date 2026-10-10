import logging
import uuid

from django.db import transaction
from decimal import Decimal

from cart.models import Cart,CartItem
from orders.models import Order,OrderAddress,OrderItem,OrderStatusHistory
from users.models import Address
from products.models import Product, ProductVariant

from products.services.tax_service import calculate_tax

SHIPPING_CHARGE = Decimal("150.00")


logger = logging.getLogger(__name__)


@transaction.atomic
def create_order(user, address_id, delivery_method, payment_method):
    address = Address.objects.filter(id=address_id, user=user).first()

    if not address:
        return None, "Selected address was not found."

    cart = Cart.objects.filter(user=user, is_active=True).first()

    if not cart:
        return None, "Your cart is empty."

    cart_items = list(CartItem.objects.filter(cart=cart).select_related("product", "product_variant").order_by("id"))


    if not cart_items:
        return None, "Your cart is empty."

    subtotal = Decimal("0.00")
    tax_amount = Decimal("0.00")

    #Store locked stock records and the quantities required
    stock_records = {}
    required_quantities = {}
    validated_items = []



    #validate every item against the latest database stock
    for cart_item in cart_items:
        #lock the product row while checking its current state
        product = (Product.objects.select_for_update(of=("self",)).filter(id=cart_item.product_id).first())

        if not product or not product.is_active:
            return None, "One of the products in your cart is unavailable."

        if cart_item.quantity <= 0:
            return None, "Invalid product quantity in your cart."

        #pots with variants use variant stock
        if cart_item.product_variant_id:
            variant = (ProductVariant.objects.select_for_update(of=("self",)).filter(id=cart_item.product_variant_id,product_id=product.id,).first())

            if not variant or not variant.is_active:
                return None, "One of the product variants is unavailable."

            stock_key = ("variant", variant.id)
            stock_object = variant


        else:
            #products without variants use product stock
            stock_key = ("product", product.id)
            stock_object = product

        #keep one stock record per product or variant
        if stock_key not in stock_records:
            stock_records[stock_key] = stock_object
            required_quantities[stock_key] = 0

        required_quantities[stock_key] += cart_item.quantity

        validated_items.append((cart_item, product, stock_key))


    #check total required quantities before changing any stock.
    for stock_key, required_quantity in required_quantities.items():
        stock_object = stock_records[stock_key]

        if stock_object.stock_quantity < required_quantity:
            if stock_object.stock_quantity < required_quantity:
                return None, (
                    f"Insufficient stock for"
                    f"{getattr(stock_object, 'name', 'selected product variant')}"
                    "Please update your cart and try again.")


    #calculate order totals after stock validation.
    for cart_item, product, stock_key in validated_items:
        item_total = cart_item.unit_price * cart_item.quantity
        subtotal += item_total
        tax_amount += calculate_tax(product, item_total)

    # Apply the shipping charge to every order.
    shipping_amount = SHIPPING_CHARGE

    #create the order.
    order = Order.objects.create(
        user=user,
        address=None,
        coupon_id=None,
        order_number=f"VERDE--{uuid.uuid4().hex[:10].upper()}",
        delivery_method=delivery_method,
        payment_method=payment_method,
        discount_amount=Decimal("0.00"),
        shipping_amount=shipping_amount,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=subtotal + shipping_amount + tax_amount,
        status="PLACED",)

    #save the delivery address.
    order_address = OrderAddress.objects.create(
        order=order,
        address_label=address.address_label,
        custom_label=address.custom_label,
        full_name=address.full_name,
        phone=address.phone,
        address_line1=address.address_line1,
        address_line2=address.address_line2,
        city=address.city,
        state=address.state,
        country=address.country,
        pin=int(address.pin),)
    order.address = order_address
    order.save(update_fields=["address"])

    #create order items.
    for cart_item, product, stock_key in validated_items:
        OrderItem.objects.create(
            order=order,
            product=product,
            product_variant=cart_item.product_variant,
            product_name=product.name,
            quantity=cart_item.quantity,
            unit_price=cart_item.unit_price,
            total_price=cart_item.unit_price * cart_item.quantity,
            discount_amount=Decimal("0.00"),
            stock_deducted=True,
        )

    #deduct stock exactly once when placing the order.
    for stock_key, required_quantity in required_quantities.items():
        stock_object = stock_records[stock_key]
        stock_object.stock_quantity -= required_quantity
        stock_object.save(update_fields=["stock_quantity", "updated_at"])

    #create order status history.
    OrderStatusHistory.objects.create(order=order,status="PLACED",)

    #clear and deactivate the cart after successful order creation.
    cart.items.all().delete()
    cart.is_active = False
    cart.save(update_fields=["is_active", "updated_at"])

    logger.info("Order created successfully: %s for user %s",order.order_number,user,)
    
    return order, None