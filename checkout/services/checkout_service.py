import logging
import uuid

from django.db import transaction
from decimal import Decimal

from cart.models import Cart,CartItem
from orders.models import Order,OrderAddress,OrderItem,OrderStatusHistory
from users.models import Address
from products.models import Product, ProductVariant

from products.services.tax_service import calculate_tax
from orders.task import send_order_confirmation_email

from coupons.models import Coupon,CouponUsage
from coupons.services.coupon_service import (is_coupon_valid,is_coupon_usage_available,is_minimum_order_amount_met,calculate_coupon_discount,)
from wallet.services.wallet_service import debit_wallet

SHIPPING_CHARGE = Decimal("150.00")
SUPPORTED_PAYMENT_METHODS = {"Cash on Delivery", "Razorpay", "Wallet"}


logger = logging.getLogger(__name__)


def validate_checkout_coupon(coupon_code, subtotoal):
    subtotoal = Decimal(str(subtotoal))

    coupon = Coupon.objects.filter(code__iexact=coupon_code.strip()).first()

    if not coupon:
        return None, Decimal("0.00"), "Coupon code not found"
    if not is_coupon_valid(coupon):
        return None, Decimal("0.00"), "This coupon is inactive or expired"
    if not is_coupon_usage_available(coupon):
        return None, Decimal("0.00"), "This coupon has reached its usage limit"
    if not is_minimum_order_amount_met(coupon,subtotoal):
        return None, Decimal("0.00"), ( f"Minimum product subtotal for this coupon is ₹{coupon.minimum_order_amount}.")

    discount = calculate_coupon_discount(coupon, subtotoal)

    return coupon, discount, None


@transaction.atomic
def create_pending_razorpay_order(user, address_id, delivery_method,coupon_id=None):
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
    tax_amount =Decimal("0.00")
    validated_items = []

    for cart_item in cart_items:
        product = Product.objects.filter(id=cart_item.product_id,is_active=True,).first()

        if not product or cart_item.quantity <=0:
            return None, "A product in your cart is unavailable."

        if cart_item.product_variant_id:
            variant = ProductVariant.objects.filter(id=cart_item.product_variant_id,product_id=product.id,is_active=True).first()
            if not variant:
                return None, "A product variant is unavailable"

            stock_object =variant
        else:
            stock_object = product

        if stock_object.stock_quantity < cart_item.quantity:
            return None, f"Insufficient stock for {product.name}"

        item_total = cart_item.unit_price * cart_item.quantity
        subtotal += item_total
        tax_amount += calculate_tax(product, item_total)
        validated_items.append((cart_item,product))

    # Validate the selected coupon against the calculated product subtotal.
    coupon = None
    discount_amount = Decimal("0.00")

    if coupon_id:
        coupon, discount_amount, coupon_error = validate_checkout_coupon(
            Coupon.objects.filter(id=coupon_id).values_list("code", flat=True).first()
            or "",
            subtotal,
        )
        if coupon_error:
            return None, coupon_error

    # Apply the fixed shipping charge and subtract the coupon discount.
    shipping_amount = SHIPPING_CHARGE
    total_amount = subtotal + shipping_amount + tax_amount - discount_amount

    order = Order.objects.create(
        user=user,
        address=None,
        coupon_id=coupon.id if coupon else None,
        order_number=f"VERDE--{uuid.uuid4().hex[:10].upper()}",
        delivery_method=delivery_method,
        payment_method="Razorpay",
        payment_status="PENDING",
        discount_amount=discount_amount,
        shipping_amount=shipping_amount,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status="PLACED",
    )

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

    for cart_item, product in validated_items:
        OrderItem.objects.create(
            order=order,
            product=product,
            product_variant=cart_item.product_variant,
            product_name=product.name,
            quantity=cart_item.quantity,
            unit_price=cart_item.unit_price,
            total_price=cart_item.unit_price * cart_item.quantity,
            discount_amount=Decimal("0.00"),
            stock_deducted=False,
        )

    OrderStatusHistory.objects.create(order=order, status ="PLACED")
    logger.info("Pending Razorpay order created: %s", order.order_number,)
    return order, None

@transaction.atomic
def finalize_razorpay_order(order_id, razorpay_payment_id):# Accept the payment ID returned by Razorpay.
    order = Order.objects.select_for_update().filter(id=order_id).first()

    if not order:
        return None, "Order not found"

    #prevent duplicate processing of an already paid order
    if order.payment_status == "PAID":
        return order, None

    if order.payment_status != "PENDING":
        return None, "Order is not awaiting payment."

    order_items = list(OrderItem.objects.filter(order=order).select_related("product", "product_variant"))

    if not order_items:
        return None, "Order has no items"

    #lock and validate stock before deducting anything
    stock_records ={}
    for item in order_items:
        if item.product_variant_id:
            stock = ProductVariant.objects.select_for_update().filter(id=item.product_variant_id, product_id = item.product_id, is_active=True).first()
            key = ("variant", item.product_variant_id)
        else:
            stock = Product.objects.select_for_update().filter(id =item.product_id, is_active=True).first()
            key =("product", item.product_id)

        if not stock:
            return None, "A product is no longer available"

        stock_records.setdefault(key, stock)



    #check combined quantities when an item references the  same stock record.
    required_quantities={}
    for item in order_items:
        key = (
            ("variant", item.product_variant_id)
            if item.product_variant_id
            else ("product", item.product_id)
        )
        required_quantities[key] = (
            required_quantities.get(key, 0) + item.quantity
        )

    for key, quantity in required_quantities.items():
        if stock_records[key].stock_quantity < quantity:
            return None, "Insufficeient stock to complete this order"

    #deduct stock only all items pass validation
    for key, quantity in required_quantities.items():
        stock = stock_records[key]
        stock.stock_quantity -= quantity
        stock.save(update_fields=["stock_quantity", "updated_at"])

    for item in order_items:
        item.stock_deducted = True
        item.save(update_fields=["stock_deducted"])

    if order.coupon_id:
        coupon = Coupon.objects.select_for_update().filter(id=order.coupon_id).first()
        if coupon:
            usage, created= CouponUsage.objects.get_or_create(coupon=coupon, user=order.user, order=order, defaults={"discount_amount":order.discount_amount})
            if created:
                coupon.used_count +=1
                coupon.save(update_fields=["used_count"])

    order.payment_status = "PAID"
    order.razorpay_payment_id = razorpay_payment_id
    order.save(update_fields=["payment_status", "razorpay_payment_id", "updated_at"])

    #clear all cart only after successfull payment finalization
    cart = Cart.objects.filter(user=order.user, is_active=True).first()
    if cart:
        cart.items.all().delete()
        cart.is_active = False
        cart.save(update_fields=["is_active", "updated_at"])

    logger.info("Razorpay payment finalized for order %s", order.order_number)
    transaction.on_commit(lambda: send_order_confirmation_email.delay(order.id))

    return order, None



@transaction.atomic
def create_order(user, address_id, delivery_method, payment_method,coupon_id=None):

    if not isinstance(payment_method, str) or payment_method not in SUPPORTED_PAYMENT_METHODS:
        return None, "Unsupported payment method."

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

    coupon = None
    discount_amount = Decimal("0.00")

    if coupon_id:
        coupon = Coupon.objects.select_for_update().filter(id=coupon_id).first()

        if not coupon:
            return None, "Select coupon was not found"

        coupon, discount_amount,coupon_error = validate_checkout_coupon(coupon.code,subtotal)

        if coupon_error:
            return None, coupon_error


    #apply the shipping charge to every order
    shipping_amount = SHIPPING_CHARGE


    #calculate the final total before processing payment
    total_amount = subtotal + shipping_amount + tax_amount - discount_amount
    order_number = f"VERDE--{uuid.uuid4().hex[:10].upper()}"

    # Debit the wallet before creating the order.
    if payment_method == "Wallet":
        try:
            debit_wallet(
                user=user,
                amount=total_amount,
                reference_id=order_number,
                transaction_id=f"ORDER-PAYMENT-{order_number}",
            )
        except ValueError as error:
            return None, str(error)

    #wallet payments are paid immediately; other methods remain pending
    order = Order.objects.create(
        user=user,
        address=None,
        coupon_id=coupon.id if coupon else None,
        order_number=order_number,
        delivery_method=delivery_method,
        payment_method=payment_method,
        payment_status="PAID" if payment_method == "Wallet" else "PENDING",
        discount_amount=discount_amount,
        shipping_amount=shipping_amount,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status="PLACED",
    )
    if coupon:
        CouponUsage.objects.create(coupon=coupon,user=user,order=order,discount_amount=discount_amount)
        coupon.used_count +=1
        coupon.save(update_fields=["used_count"])

    #save the delivery address
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

    #create order items
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

    transaction.on_commit(lambda: send_order_confirmation_email.delay(order.id))

    return order, None