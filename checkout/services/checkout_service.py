import logging
import uuid

from django.db import transaction
from decimal import Decimal

from cart.models import Cart,CartItem
from orders.models import Order,OrderAddress,OrderItem,OrderStatusHistory
from users.models import Address

SHIPPING_CHARGE = Decimal("150.00")
FREE_SHIPPING_THRESHOLD = Decimal("1000.00")


logger = logging.getLogger(__name__)

@transaction.atomic
def create_order(user,address_id, delivery_method,payment_method):
    #for selected address
    address = Address.objects.filter(id=address_id, user=user).first()

    if not address:
        return None,"Selected address was not found."

    #get active cart
    cart = Cart.objects.filter(user=user, is_active=True).first()

    if not cart:
        return None, "Your cart is empty."

    #get cart item
    cart_items = (CartItem.objects.filter(cart=cart).select_related("product", "product_variant"))

    if not cart_items.exists():
        return None, "Your cart is empty"

    subtotal = Decimal("0.00")

    for cart_item in cart_items:

        #Check cart active
        if not cart_item.product.is_active:
            return None, "One of the product in your cart is unavailable"

        #check variant is active
        if cart_item.product_variant and not cart_item.product_variant.is_active:
            return None, "One of the product variants is unavailable."

        subtotal += cart_item.unit_price * cart_item.quantity

    #shipping charge
    if subtotal >= FREE_SHIPPING_THRESHOLD:
        shipping_amount = Decimal("0.00")
    else:
        shipping_amount = SHIPPING_CHARGE

    #create variant
    order = Order.objects.create(
        user= user,
        address=None,
        coupon_id=None,
        order_number =f"VERDE--{uuid.uuid4().hex[:10].upper()}",
        delivery_method = delivery_method,
        payment_method = payment_method,
        discount_amount =0,
        shipping_amount = shipping_amount,
        subtotal = subtotal,
        total_amount=subtotal+shipping_amount,
        status="PLACED",
    )

    #order address snapshot
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
        pin=int(address.pin),
    )

    order.address = order_address
    order.save(update_fields=["address"])

    #create order items
    for cart_item in cart_items:
        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            product_variant=cart_item.product_variant,
            product_name=cart_item.product.name,
            quantity=cart_item.quantity,
            unit_price=cart_item.unit_price,
            total_price=cart_item.unit_price * cart_item.quantity,
            discount_amount=0,
        )

    #create initial order status history
    OrderStatusHistory.objects.create(order=order, status = "PLACED",)
    #clr cart after order
    cart.items.all().delete()
    cart.is_active = False
    cart.save(update_fields=["is_active","updated_at"])

    logger.info("Cart cleared and deactivated after order: %s", order.order_number)

    logger.info("Order created successfully: %s for user %s", order.order_number,user)

    return order,None
