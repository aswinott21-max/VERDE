from decimal import Decimal
from django.db.models import Sum,Count,Q
from django.db.models.functions import TruncDate, TruncMonth
from datetime import date, timedelta
from django.db.models import OuterRef, Subquery

from orders.models import Order, OrderItem,Refund,Return
from coupons.models import CouponUsage
from products.models import ProductImage
from referrals.models import Referral, ReferralOffer, ReferralReward


def get_sales_report(start_date, end_date, period=None):
    #calculate sales totals for the selected date range
    orders = Order.objects.filter(payment_status="PAID",created_at__date__gte=start_date,created_at__date__lte=end_date).exclude(status="CANCELLED")
    totals = orders.aggregate(
        order_count=Sum("id", distinct=True),
        subtotal=Sum("subtotal"),
        shipping=Sum("shipping_amount"),
        tax=Sum("tax_amount"),
        discounts=Sum("discount_amount"),
        order_amount=Sum("total_amount"),
    )

    coupon_discount = CouponUsage.objects.filter(order__in=orders).aggregate(amount=Sum("discount_amount"))["amount"] or Decimal("0.00")
    coupon_details = CouponUsage.objects.filter(order__in=orders).values("coupon__code","coupon__coupon_name",).annotate(usage_count=Count("id"),total_discount=Sum("discount_amount"),).order_by("-total_discount")

    if period == "year":
        # Group report revenue by month for the yearly chart (January – December)
        chart_sales = (
            orders.annotate(chart_month=TruncMonth("created_at"))
            .values("chart_month")
            .annotate(sales=Sum("total_amount"))
            .order_by("chart_month")
        )
        sales_by_month = {}
        for entry in chart_sales:
            entry_date = entry["chart_month"]
            if hasattr(entry_date, "date"):
                entry_date = entry_date.date()
            if entry_date:
                month_num = entry_date.month
                sales_by_month[month_num] = sales_by_month.get(month_num, Decimal("0.00")) + (entry["sales"] or Decimal("0.00"))

        report_year = start_date.year
        chart_dates = [date(report_year, month, 1) for month in range(1, 13)]
        chart_labels = [day.strftime("%b") for day in chart_dates]
        chart_values = [sales_by_month.get(month, Decimal("0.00")) for month in range(1, 13)]
        max_sales = max(chart_values, default=Decimal("0.00"))

        chart_data = [
            {
                "label": label,
                "sales": sales,
                "height": round(float(sales / max_sales * 100), 1) if max_sales else 0,
            }
            for label, sales in zip(chart_labels, chart_values)
        ]
    else:
        # group report revenue by date and calculate bar heights for the dashboard chart
        chart_sales = orders.annotate(
            period_date=TruncDate("created_at")
        ).values("period_date").annotate(
            sales=Sum("total_amount")
        ).order_by("period_date")
        sales_by_period = {
            entry["period_date"]: entry["sales"] or Decimal("0.00")
            for entry in chart_sales
        }

        chart_dates = [
            start_date + timedelta(days=offset)
            for offset in range((end_date - start_date).days + 1)
        ]
        chart_values = [sales_by_period.get(day, Decimal("0.00")) for day in chart_dates]
        max_sales = max(chart_values, default=Decimal("0.00"))

        chart_data = [
            {
                "label": day.strftime("%d %b"),
                "sales": sales,
                "height": round(float(sales / max_sales * 100), 1) if max_sales else 0,
            }
            for day, sales in zip(chart_dates, chart_values)
        ]
    refunds = Refund.objects.filter(status ="COMPLETED",return_request__order_item__order__in=orders,).aggregate(amount=Sum("amount"))["amount"] or Decimal("0.00")

    subtotal = totals["subtotal"] or Decimal("0.00")
    shipping = totals["shipping"] or Decimal("0.00")
    tax = totals["tax"] or Decimal("0.00")
    discounts = totals["discounts"] or Decimal("0.00")
    order_amount = totals["order_amount"] or Decimal("0.00")

    product_image = ProductImage.objects.filter(
        product_id=OuterRef("product_id")
    ).order_by(
            "-is_primary", "sort_order"
    ).values("image_url")[:1]


    best_selling_products = OrderItem.objects.filter(
        order__in=orders,
        product__isnull=False,
    ).exclude(
        item_status="CANCELLED"
    ).values(
        "product_id", "product_name"
    ).annotate(
        units_sold=Sum("quantity"),
        image_url=Subquery(product_image),
    ).order_by("-units_sold")


    best_selling_categories = OrderItem.objects.filter(
        order__in=orders,
        product__isnull=False,
    ).exclude(
        item_status="CANCELLED"
    ).values(
        "product__category_id",
        "product__category__name",
    ).annotate(
        units_sold=Sum("quantity")
    ).order_by("-units_sold")

    #count orders by their current lifecycle status
    operational_orders = Order.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    ).exclude(status="CANCELLED")

    operations_summary = {
        "delivered": operational_orders.filter(status="DELIVERED").count(),
        "placed": operational_orders.filter(status="PLACED").count(),
        "shipped": operational_orders.filter(status="SHIPPED").count(),
        "returned": operational_orders.filter(status="RETURNED").count(),
    }

    #summarize paid orders by payment method
    payment_summary = orders.values("payment_method").annotate(
        order_count=Count("id")
    ).order_by("-order_count")

    return {
        "orders": orders.order_by("-created_at"),
        "sales_count": orders.count(),
        "gross_amount": subtotal + shipping + tax,
        "discount_amount": discounts,
        "coupon_discount" :coupon_discount,
        "coupon_details": coupon_details,
        "chart_data":chart_data,
        "best_selling_products": best_selling_products,
        "best_selling_categories": best_selling_categories,
        "operations_summary": operations_summary,
        "payment_summary": payment_summary,
        "order_amount": order_amount,
        "refund_amount": refunds,
        "net_revenue": order_amount - refunds,
        "start_date": start_date,
        "end_date": end_date,  
    }

def get_referral_summary():
    """Return all-time referral metrics for the admin sales report."""

    referral_counts = Referral.objects.aggregate(
        total=Count("id"),
        successful=Count(
            "id",
            filter=Q(status=Referral.Status.REWARDED),
        ),
    )

    rewards_distributed = (
        ReferralReward.objects.filter(
            status=ReferralReward.Status.CREDITED,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    return {
        **referral_counts,
        "rewards_distributed": rewards_distributed,
        "offer_active": ReferralOffer.objects.filter(is_active=True).exists(),
    }