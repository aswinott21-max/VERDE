
import re
from datetime import timedelta

from orders.models import Order


ORDER_NUMBER_PATTERN = re.compile(r"\bVERDE--[A-F0-9]{10}\b", re.IGNORECASE)


def get_customer_order_context(user, user_message):
    """
    Return verified order information for the authenticated customer.
    This function only reads database records.
    """

    if not user or not user.is_authenticated:
        return None

    message = user_message.lower()

    # Only process messages related to the customer's orders.
    order_keywords = (
        "order", "delivery", "refund", "return", "payment"
    )

    if not any(keyword in message for keyword in order_keywords):
        return None

    order_number_match = ORDER_NUMBER_PATTERN.search(user_message)

    orders = (
        Order.objects.filter(user=user)
        .prefetch_related("items__returns__refunds", "status_history")
    )

    if order_number_match:
        order = orders.filter(
            order_number__iexact=order_number_match.group()
        ).first()
    else:
        order = orders.order_by("-created_at").first()

    if not order:
        return "No matching order was found in your account."

    delivery_start = order.created_at + timedelta(days=3)
    delivery_end = order.created_at + timedelta(days=4)

    details = [
        f"Order number: {order.order_number}",
        f"Order status: {order.status}",
        f"Payment method: {order.payment_method}",
        f"Payment status: {order.payment_status}",
        f"Order total: ₹{order.total_amount}",
    ]

    if order.status not in ("DELIVERED", "CANCELLED", "RETURNED"):
        details.append(
            f"Estimated delivery: {delivery_start:%d %b %Y} "
            f"to {delivery_end:%d %b %Y}"
        )

    for item in order.items.all():
        for return_request in item.returns.all():
            details.append(
                f"Return for {item.product_name}: "
                f"{return_request.status}"
            )

            for refund in return_request.refunds.all():
                details.append(
                    f"Refund status: {refund.status}; "
                    f"Refund amount: ₹{refund.amount}"
                )

    return "\n".join(details)
