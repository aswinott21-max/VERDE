
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from orders.models import Order

logger = logging.getLogger(__name__)


@shared_task
def send_order_confirmation_email(order_id):
    try:
        order = Order.objects.select_related("user").get(id=order_id)
    except Order.DoesNotExist:
        logger.warning("Order %s not found; confirmation email skipped.", order_id)
        return

    if not order.user or not order.user.email:
        logger.warning("Order %s has no customer email.", order.order_number)
        return

    subject = f"VERDÉ order confirmation - {order.order_number}"
    message = (
        f"Hello {order.user.full_name or order.user.email},\n\n"
        f"Your order has been placed successfully.\n"
        f"Order number: {order.order_number}\n"
        f"Order date: {order.created_at:%d %B %Y, %I:%M %p}\n"
        f"Total amount: ₹{order.total_amount}\n\n"
        "Thank you for shopping with VERDÉ!"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Failed to send confirmation email for order %s",
            order.order_number,
        )
        raise