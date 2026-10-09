import logging
from django.db import transaction

from orders.models import Order,OrderStatusHistory,Return,OrderItem
from products.services.tax_service import calculate_tax

logger = logging.getLogger(__name__)

@transaction.atomic
def cancel_order(user,order_number,cancellation_reason=None):

    #find order of loggedin user
    order = (Order.objects.select_for_update().filter(order_number = order_number, user=user).first())

    if not order:
        return None, "Order not found."

    if order.status not in ["PLACED","PROCESSING","SHIPPED","OUT_FOR_DELIVERY",]:
        return None, "This order cannot be cancelled"

    
    order.status = "CANCELLED"
    order.cancellation_reason =cancellation_reason
    order.save(update_fields=["status","cancellation_reason","updated_at"])

    OrderStatusHistory.objects.create(order=order,status="CANCELLED")

    logger.info("Cancel order requested: %s | User:%s", order_number, user)

    return order, None

@transaction.atomic
def return_order(user, order_number, return_reason):
    order = (Order.objects.select_for_update().filter(order_number = order_number,user=user).first())

    if not order:
        return None, "Order not found."
    #return only after delivered
    if order.status != "DELIVERED":
        return None,"Only delivered orders can be returned"

    #get only items not cancelled
    items = order.items.filter(item_status="ACTIVE").exclude(returns__isnull=False)

    if not items.exists():
        return None, "No eligible items available for return."

    for item in items:

        Return.objects.create(order_item=item,user=user,reason=return_reason,status="REQUESTED", refund_amount=item.total_price,)

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

    item = (order.items.filter(id=order_item_id,item_status ="ACTIVE").first())

    if not item:
        return None, "Order item not found or cannot be returned"

    #check its already returned
    if Return.objects.filter(order_item=item).exists():
        return None, "This item has already been returned."

    #create return request
    return_request = Return.objects.create(order_item=item, user=user,reason=return_reason,user_add_note=user_add_note,status="REQUESTED",refund_amount=item.total_price,)

    logger.info("Item return requested: %s | Item: %s | User: %s | Reason: %s", order_number,item.id, user, return_reason)

    return return_request,None

@transaction.atomic
def update_return_status(return_id, new_status):
    return_request = (
        Return.objects
        .select_for_update(of=("self",))
        .select_related(
            "order_item",
            "order_item__order",
            "order_item__product",
            "order_item__product_variant",
        )
        .filter(id=return_id)
        .first()
    )

    if not return_request:
        return None, "Return request not found"

    allowed_transactions = {
        "REQUESTED": ["PICKED"],
        "PICKED": ["INSPECT_APPROVED", "INSPECT_REJECTED"],
        "INSPECT_APPROVED": [],
        "INSPECT_REJECTED": [],
    }

    old_status = return_request.status
    allowed_next_statuses = allowed_transactions.get(old_status, [])

    if new_status not in allowed_next_statuses:
        return None, f"Return cannot move from {old_status} to {new_status}"

    #restore stock only when the returned item passes inspection
    if new_status == "INSPECT_APPROVED":

        order_item = return_request.order_item

        if order_item.product_variant:
            order_item.product_variant.stock_quantity += order_item.quantity
            order_item.product_variant.save(
                update_fields=["stock_quantity"]
            )

        else:
            order_item.product.stock_quantity += order_item.quantity
            order_item.product.save(
                update_fields=["stock_quantity"]
            )

    return_request.status = new_status
    return_request.save(update_fields=["status", "updated_at"])

    logger.info(
        "Return status updated: Return #%s | %s -> %s",
        return_id,
        old_status,
        new_status,
    )

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
def cancel_order_item(user, order_number, order_item_id, cancellation_reason=None):
    
    order_item = (OrderItem.objects.select_for_update().select_related("order", "product",).filter(id=order_item_id,order__order_number=order_number,order__user=user,).first())

    if not order_item:
        return None, "Order item not found."

    order = order_item.order

    #only allow cancellation while the order is still cancellable
    if order.status not in ["PLACED", "PROCESSING", "SHIPPED", "OUT_FOR_DELIVERY"]:
        return None, "This order item cannot be cancelled."

    #prevent cancelling the same item twice
    if order_item.item_status == "CANCELLED":
        return None, "This order item is already cancelled."

    #reduce the order subtotal and tax for the cancelled item
    cancelled_item_total = order_item.total_price
    cancelled_item_tax = calculate_tax(order_item.product,cancelled_item_total)
    order.subtotal -= cancelled_item_total
    order.tax_amount -= cancelled_item_tax
    order.total_amount -= cancelled_item_total + cancelled_item_tax
    order.save(update_fields=["subtotal","tax_amount","total_amount","updated_at",])

    #mark only this item as cancelled
    order_item.item_status = "CANCELLED"
    order_item.cancellation_reason = cancellation_reason
    order_item.save(update_fields=["item_status", "cancellation_reason"])

    #Check if any active items are left in the order
    active_items_exist = order.items.filter(item_status="ACTIVE").exists()

    # If no active items remain, cancel the entire order
    if not active_items_exist:
        order.status = "CANCELLED"
        order.save(update_fields=["status", "updated_at"])


    logger.info("Order item cancelled: %s | Order: %s | User: %s",order_item.id,order_number,user,)

    return order_item, None

@transaction.atomic
def update_order_status(order_number, new_status):
    order = (
        Order.objects
        .select_for_update()
        .filter(order_number=order_number)
        .first()
    )

    if not order:
        return None, "Order not found"

    old_status = order.status

    allowed_trasactions = {
        "PLACED": ["PROCESSING", "CANCELLED"],
        "PROCESSING": ["SHIPPED", "CANCELLED"],
        "SHIPPED": ["OUT_FOR_DELIVERY", "CANCELLED"],
        "OUT_FOR_DELIVERY": ["DELIVERED", "CANCELLED"],
        "DELIVERED": ["RETURNED"],
        "CANCELLED": [],
        "RETURNED": [],
    }

    allowed_next_statuses = allowed_trasactions.get(
        order.status,
        []
    )

    if new_status not in allowed_next_statuses:
        return None, f"Order cannot move from {order.status} to {new_status}."


    #deduct stock only when the order is delivered
    if new_status == "DELIVERED":

        # Check stock for every active order item
        for item in order.items.select_related(
            "product",
            "product_variant"
        ):

            if item.item_status != "ACTIVE":
                continue

            if item.product_variant:
                if item.product_variant.stock_quantity < item.quantity:
                    return None, f"Not enough stock for {item.product_name}."

            else:
                if item.product.stock_quantity < item.quantity:
                    return None, f"Not enough stock for {item.product_name}."


        # Deduct stock after all items pass the stock check
        for item in order.items.select_related(
            "product",
            "product_variant"
        ):

            if item.item_status != "ACTIVE":
                continue

            if item.product_variant:
                item.product_variant.stock_quantity -= item.quantity
                item.product_variant.save(
                    update_fields=["stock_quantity"]
                )

            else:
                item.product.stock_quantity -= item.quantity
                item.product.save(
                    update_fields=["stock_quantity"]
                )


    order.status = new_status
    order.save(
        update_fields=["status", "updated_at"]
    )

    OrderStatusHistory.objects.create(
        order=order,
        status=new_status
    )

    logger.info(
        "Order status updated: %s | %s -> %s",
        order_number,
        old_status,
        new_status,
    )

    return order, None