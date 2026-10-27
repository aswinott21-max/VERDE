import logging
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from datetime import timedelta


from orders.models import Order,OrderStatusHistory,Return,OrderItem, Refund
from products.models import Product,ProductVariant
from wallet.models import WalletTransaction
from products.services.tax_service import calculate_tax
from wallet.services.wallet_service import credit_wallet

logger = logging.getLogger(__name__)

CANCELLABLE_ORDER_STATUSES = {
    "PLACED",
    "PROCESSING",
    "SHIPPED",
    "OUT_FOR_DELIVERY",
}

def _get_return_window_error(order):
    #Check whether an order is still within its 3-calendar-day return window
    delivery_history = (order.status_history.filter(status="DELIVERED").order_by("created_at").first())

    if not delivery_history:
        return "Delivery date is unavailable. Please contact support."

    delivery_date = timezone.localdate(delivery_history.created_at)
    last_return_date = delivery_date + timedelta(days=3)

    if timezone.localdate() > last_return_date:
        return "The 3-day return window has expired"

    return None


def _calculate_return_refund_amount(order, item):
    item_tax = calculate_tax(item.product, item.total_price)
    item_discount = (
        (order.discount_amount * item.total_price / order.subtotal).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        if order.subtotal > 0
        else Decimal("0.00")
    )
    return item.total_price + item_tax - item_discount


@transaction.atomic
def cancel_order(user, order_number, cancellation_reason=None):
    order = (Order.objects.select_for_update().filter(order_number=order_number, user=user).first())

    if not order:
        return None, "Order not found."

    return _cancel_locked_order(order, cancellation_reason=cancellation_reason)


def _cancel_locked_order(order, cancellation_reason=None):
    """Cancel an already locked order and apply its stock and wallet effects."""
    if order.status not in CANCELLABLE_ORDER_STATUSES:
        return None, "This order cannot be cancelled."

    # All paid methods follow VERDÉ's policy of refunding to its internal wallet.
    # For COD, PAID is the system's collection indicator; pending COD is not refunded.
    if order.payment_status == "PAID" and order.total_amount > 0:
        if not order.user_id:
            return None, "Order has no customer account for the wallet refund."

        transaction_id = f"CANCEL-REFUND-{order.id}"
        existing_credit = (
            WalletTransaction.objects.select_for_update()
            .select_related("wallet")
            .filter(transaction_id=transaction_id)
            .first()
        )

        if existing_credit:
            if (
                existing_credit.wallet.user_id != order.user_id
                or existing_credit.amount != order.total_amount
                or existing_credit.transaction_type != "CREDIT"
                or existing_credit.reference_id != order.order_number
            ):
                return None, "Existing cancellation wallet transaction requires review."
        else:
            try:
                credit_wallet(
                    user=order.user,
                    amount=order.total_amount,
                    reference_id=order.order_number,
                    transaction_id=transaction_id,
                )
            except ValueError as error:
                return None, str(error)

    # Restore stock once, only for active items whose stock was deducted.
    items = list(order.items.select_for_update().filter(item_status="ACTIVE", stock_deducted=True).order_by("id"))

    for item in items:
        if item.product_variant_id:
            variant = (ProductVariant.objects.select_for_update().filter(id=item.product_variant_id).first())

            if variant:
                variant.stock_quantity += item.quantity
                variant.save(update_fields=["stock_quantity"])

        else:
            product = (Product.objects.select_for_update().filter(id=item.product_id).first())

            if product:
                product.stock_quantity += item.quantity
                product.save(update_fields=["stock_quantity"])


        item.stock_deducted = False
        item.save(update_fields=["stock_deducted"])


    order.status = "CANCELLED"
    order.cancellation_reason = cancellation_reason
    order.save(update_fields=["status", "cancellation_reason", "updated_at"])

    OrderStatusHistory.objects.create(order=order,status="CANCELLED",)

    logger.info("Order cancelled: %s | User: %s", order.order_number, order.user)

    return order, None

@transaction.atomic
def return_order(user, order_number, return_reason):
    order = (Order.objects.select_for_update().filter(order_number = order_number,user=user).first())

    if not order:
        return None, "Order not found."
    #return only after delivered
    if order.status != "DELIVERED":
        return None,"Only delivered orders can be returned"

    return_window_error =_get_return_window_error(order)
    if return_window_error:
        return None, return_window_error

    #get only items not cancelled
    items = order.items.filter(item_status="ACTIVE").exclude(returns__isnull=False)

    if not items.exists():
        return None, "No eligible items available for return."

    for item in items:

        Return.objects.create(
            order_item=item,
            user=user,
            reason=return_reason,
            status="REQUESTED",
            refund_amount=_calculate_return_refund_amount(order, item),
        )

    logger.info("Returned requested: %s |User: %s |Reason: %s", order_number, user, return_reason,)

    return order, None

@transaction.atomic
def return_order_item(user, order_number, order_item_id, return_reason, user_add_note=None):

    order =(Order.objects.select_for_update().filter(order_number=order_number,user=user,).first())

    if not order:
        return None,"Order not found."

    #return only after delivery
    if order.status != "DELIVERED":
        return None, "Only delivered orders can be returned"

    return_window_error =_get_return_window_error(order)
    if return_window_error:
        return None, return_window_error

    item = (order.items.filter(id=order_item_id,item_status ="ACTIVE").first())

    if not item:
        return None, "Order item not found or cannot be returned"

    #check its already returned
    if Return.objects.filter(order_item=item).exists():
        return None, "This item has already been returned."


    refund_amount = _calculate_return_refund_amount(order, item)
    #create return request
    return_request = Return.objects.create(order_item=item, user=user,reason=return_reason,user_add_note=user_add_note,status="REQUESTED",refund_amount=refund_amount,)

    logger.info("Item return requested: %s | Item: %s | User: %s | Reason: %s", order_number,item.id, user, return_reason)

    return return_request,None


@transaction.atomic
def update_return_status(return_id, new_status):
    #lock the return request to prevent concurrent approval processing
    return_request = (Return.objects.select_for_update(of=("self",)).select_related("order_item","order_item__order","order_item__product","order_item__product_variant",).filter(id=return_id).first())

    if not return_request:
        return None, "Return request not found."

    allowed_transactions = {
        "REQUESTED": ["PICKED"],
        "PICKED": ["INSPECT_APPROVED", "INSPECT_REJECTED"],
        "INSPECT_APPROVED": [],
        "INSPECT_REJECTED": [],
    }

    old_status = return_request.status
    if new_status not in allowed_transactions.get(old_status, []):
        return None, f"Return cannot move from {old_status} to {new_status}."

    if new_status == "INSPECT_APPROVED":
        if return_request.order_item.order.payment_status != "PAID":
            return None, "Payment must be confirmed before approving return"

        order_item = return_request.order_item

        #restore stock once after the return is approved
        if order_item.stock_deducted:
            if order_item.product_variant_id:
                variant = ProductVariant.objects.select_for_update().filter(id=order_item.product_variant_id).first()
                if variant:
                    variant.stock_quantity += order_item.quantity
                    variant.save(update_fields=["stock_quantity"])
            else:
                product = Product.objects.select_for_update().filter(id=order_item.product_id).first()
                if product:
                    product.stock_quantity += order_item.quantity
                    product.save(update_fields=["stock_quantity"])

            order_item.stock_deducted = False
            order_item.save(update_fields=["stock_deducted"])

        #create and process the refund only once for paid orders
        if (return_request.user_id and order_item.order.payment_status == "PAID" and return_request.refund_amount > 0):

            existing_refund = Refund.objects.select_for_update().filter(return_request=return_request).first()

            if not existing_refund:
                refund = Refund.objects.create(
                    return_request=return_request,
                    user=return_request.user,
                    amount=return_request.refund_amount,
                    status="PENDING",
                )

                wallet = credit_wallet(
                    user=return_request.user,
                    amount=refund.amount,
                    reference_id=return_request.id,
                    transaction_id=f"RETURN-REFUND-{refund.id}",
                )

                refund.wallet_transaction_id = wallet.transactions.filter(transaction_id=f"RETURN-REFUND-{refund.id}").values_list("id", flat=True).first()
                refund.processed_at = timezone.now()
                refund.status = "COMPLETED"
                refund.save(update_fields=["status","wallet_transaction_id", "processed_at", "updated_at"])

    return_request.status = new_status
    return_request.save(update_fields=["status", "updated_at"])

    logger.info("Return status updated: Return #%s | %s -> %s",return_id,old_status,new_status,)

    return return_request, None

@transaction.atomic
def update_return_note(return_id, internal_note):

    return_request =(Return.objects.select_for_update().filter(id=return_id).first())

    if not return_request:
        return None, "Return  request not found"

    return_request.internal_note = internal_note
    return_request.save(update_fields=["Internal_note", "updated_at"])

    logger.info("Return internal  note udated: Return #%s", return_id)

    return  return_request, None







@transaction.atomic
def cancel_order_item(
    user, order_number, order_item_id, cancellation_reason=None):

    order_item = (OrderItem.objects.select_for_update().select_related("order").filter(id=order_item_id,order__order_number=order_number,order__user=user,).first() )

    if not order_item:
        return None, "Order item not found."

    order = order_item.order

    #allow cancellation only before delivery
    if order.status not in ["PLACED", "PROCESSING", "SHIPPED", "OUT_FOR_DELIVERY"]:
        return None, "This order item cannot be cancelled."

    #prevent cancelling the same item twice.
    if order_item.item_status == "CANCELLED":
        return None, "This order item is already cancelled."

    #restore stock only if it was deducted at order placement
    if order_item.stock_deducted:
        if order_item.product_variant_id:
            variant = (ProductVariant.objects.select_for_update().filter(id=order_item.product_variant_id).first())

            if variant:
                variant.stock_quantity += order_item.quantity
                variant.save(update_fields=["stock_quantity"])

        else:
            product = (Product.objects.select_for_update().filter(id=order_item.product_id).first())

            if product:
                product.stock_quantity += order_item.quantity
                product.save(update_fields=["stock_quantity"])

        #Prevent restoring this items stock twice
        order_item.stock_deducted = False

    #calculate cancellec items tax and proportional coupon discount
    cancelled_item_total = order_item.total_price
    cancelled_item_tax = calculate_tax(order_item.product, cancelled_item_total)

    if order.subtotal > 0 :
        cancelled_item_discount = (order.discount_amount * cancelled_item_total / order.subtotal).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        cancelled_item_discount = Decimal("0.00")

    order_item.item_status = "CANCELLED"
    order_item.cancellation_reason = cancellation_reason
    order_item.save(update_fields=["item_status", "cancellation_reason","stock_deducted"])
    is_last_item = not order.items.filter(item_status="ACTIVE").exists()
    shipping_refund = order.shipping_amount if is_last_item else Decimal("0.00")

    refund_amount = (cancelled_item_total+cancelled_item_tax - cancelled_item_discount+shipping_refund)

    #update order totals after removing the cancelled item.
    order.subtotal -= cancelled_item_total
    order.tax_amount -= cancelled_item_tax
    order.discount_amount -= cancelled_item_discount
    order.shipping_amount -= shipping_refund
    order.total_amount -= refund_amount

    update_fields = ["subtotal", "tax_amount", "discount_amount","shipping_amount","total_amount","updated_at"]

    if is_last_item:
        order.status = "CANCELLED"
        update_fields.append("status")

    order.save(update_fields=update_fields)

    #refund the amount to wallet only if payment was completed
    if order.payment_status == "PAID" and refund_amount >0:
        credit_wallet(user=user, amount=refund_amount,reference_id=order.order_number,transaction_id=f"ITEM-CANCEL-REFUND-{order_item.id}")

    if is_last_item:
        OrderStatusHistory.objects.create(order=order,status="CANCELLED")

    logger.info("Order item cancelled: %s | Order: %s | User: %s", order_item.id, order_number,user)

    return order_item, None


@transaction.atomic
def update_order_status(order_number, new_status):


    order = (Order.objects.select_for_update().filter(order_number=order_number).first())

    if not order:
        return None, "Order not found."

    if new_status == "CANCELLED":
        return _cancel_locked_order(order)

    old_status = order.status

    allowed_transactions = {
        "PLACED": ["PROCESSING", "CANCELLED"],
        "PROCESSING": ["SHIPPED", "CANCELLED"],
        "SHIPPED": ["OUT_FOR_DELIVERY", "CANCELLED"],
        "OUT_FOR_DELIVERY": ["DELIVERED", "CANCELLED"],
        "DELIVERED": ["RETURNED"],
        "CANCELLED": [],
        "RETURNED": [],
    }

    allowed_next_statuses = allowed_transactions.get(old_status, [])

    if new_status not in allowed_next_statuses:
        return None, (f"Order cannot move from {old_status} to {new_status}.")

    #pdate the order status
    order.status = new_status
    update_fields = ["status", "updated_at"]

    if new_status == "DELIVERED" and order.payment_method == "Cash on Delivery":
        order.payment_status = "PAID"
        update_fields.append("payment_status")

    order.save(update_fields=update_fields)

    #record the status change
    OrderStatusHistory.objects.create(order=order,status=new_status,)
    logger.info("Order status updated: %s | %s -> %s",order_number,old_status,new_status,)

    return order, None

@transaction.atomic
def mark_cod_payment_collected(order_number):

    order = Order.objects.select_for_update().filter(order_number = order_number).first()

    if not order:
        return None, "Order not found"
    if order.payment_method != "Cash on Delivery":
        return None, "This order is not Cash on Delivery"
    if order.status != "DELIVERED":
        return None, "COD payment can only be collected after delivery"
    if order.payment_status == "PAID":
        return None, "This order is already paid"
    if order.payment_status != "PENDING":
        return None, "This order's payment status cannot be updated"

    order.payment_status = "PAID"
    order.save(update_fields=["payment_status", "updated_at"])

    logger.info("COD payment collected: %s", order_number)
    return order,None

# Safely process or recover an approved return refund without duplicate wallet credits.
@transaction.atomic
def process_approved_return_refund(return_id):
    return_request = (Return.objects.select_for_update().select_related("order_item__order").filter(id=return_id).first())

    if not return_request:
        return None, "Return request not found."

    if return_request.status != "INSPECT_APPROVED":
        return None, "Return must be inspection-approved before refunding."

    if return_request.order_item.order.payment_status != "PAID":
        return None, "Payment must be confirmed before refunding."

    if not return_request.user_id:
        return None, "Return has no associated user."

    if return_request.refund_amount <= 0:
        return None, "Refund amount must be greater than zero."

    refund = (Refund.objects.select_for_update().filter(return_request=return_request).first())

    if refund and refund.status == "COMPLETED":
        return refund, None

    if refund and refund.status != "PENDING":
        return None, "An existing refund requires review."

    if refund and refund.amount != return_request.refund_amount:
        return None, "Refund amount mismatch; manual review required."

    if not refund:
        refund = Refund.objects.create(
            return_request=return_request,
            user=return_request.user,
            amount=return_request.refund_amount,
            status="PENDING",
        )

    transaction_id = f"RETURN-REFUND-{refund.id}"

    # Find an earlier wallet credit before attempting another one.
    wallet_transaction = WalletTransaction.objects.select_for_update().filter(
        transaction_id=transaction_id
    ).first()

    if wallet_transaction:
        if (
            wallet_transaction.transaction_type != "CREDIT"
            or wallet_transaction.amount != refund.amount
            or wallet_transaction.wallet.user_id != refund.user_id
        ):
            return None, "Existing wallet transaction does not match this refund."

        wallet_transaction_id = wallet_transaction.id
    else:
        wallet = credit_wallet(user=refund.user,amount=refund.amount,reference_id=return_request.id,transaction_id=transaction_id,)

        wallet_transaction_id = wallet.transactions.get(transaction_id=transaction_id).id

    refund.wallet_transaction_id = wallet_transaction_id
    refund.processed_at = timezone.now()
    refund.status = "COMPLETED"
    refund.save(update_fields=["wallet_transaction_id","processed_at","status","updated_at",])
    logger.info("Approved return refund processed: Return #%s | Refund #%s",return_id,refund.id,)
    return refund, None
