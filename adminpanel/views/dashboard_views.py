from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Sum,Q
from django.db.models.functions import TruncDate, TruncMonth
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from adminpanel.decorators import admin_required
from users.models import User
from orders.models import Order, OrderItem, Return, Refund
from products.models import Product,ProductImage

@never_cache
@admin_required
def admin_dashboard_page(request):

    #Use paid, non-cancelled orders as the basis for sales figures
    today = timezone.localdate()
    chart_period = request.GET.get("period","week")
    if chart_period not in {"week","month","year"}:
        chart_period ="week"

    paid_orders = Order.objects.filter(payment_status="PAID").exclude(status="CANCELLED")

    if chart_period == "week":
        chart_start = today - timedelta(days=6)
        chart_grouping = TruncDate("created_at")
    elif chart_period == "month":
        chart_start = today.replace(day=1)
        chart_grouping = TruncDate("created_at")
    else:
        chart_start = today.replace(month=1, day=1)
        chart_grouping = TruncMonth("created_at")

    chart_sales = (
        paid_orders.filter(created_at__date__gte=chart_start,
                           created_at__date__lte=today)
        .annotate(period=chart_grouping)
        .values("period")
        .annotate(sales=Sum("total_amount"))
        .order_by("period")
    )

    #fill missing dates with zero sales and calculate relative bar heights
    sales_by_period = {}
    for entry in chart_sales:
        period_date = entry["period"]
        if hasattr(period_date, "date"):
            period_date = period_date.date()
        sales_by_period[period_date] = entry["sales"] or Decimal("0.00")

    if chart_period == "week":
        chart_dates = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        chart_labels = [day.strftime("%a") for day in chart_dates]
    elif chart_period == "month":
        chart_dates = [today.replace(day=day) for day in range(1, today.day + 1)]
        chart_labels = [day.strftime("%d") for day in chart_dates]
    else:
        chart_dates = [today.replace(month=month, day=1) for month in range(1, today.month + 1)]
        chart_labels = [day.strftime("%b") for day in chart_dates]

    chart_values = [
        sales_by_period.get(
            day.replace(day=1) if chart_period == "year" else day,
            Decimal("0.00"),
        )
        for day in chart_dates
    ]
    max_sales = max(chart_values, default=Decimal("0.00"))

    chart_data = [
        {
            "label": label,
            "sales": sales,
            "height": round(float(sales / max_sales * 100), 1) if max_sales else 0,
        }
        for label, sales in zip(chart_labels, chart_values)
    ]

    total_sales = paid_orders.aggregate(amount=Sum("total_amount"))["amount"] or Decimal("0.00")

    #remove only completed refunds belonging to eligible sales
    complete_refunds = Refund.objects.filter(status="COMPLETED", return_request__order_item__order__in=paid_orders,).aggregate(amount=Sum("amount"))["amount"] or Decimal("0.00")

    net_revenue = total_sales - complete_refunds

    today_orders = paid_orders.filter(created_at__date=today)
    today_sales = today_orders.aggregate(amount=Sum("total_amount"))["amount"] or Decimal("0.00")

    today_refunds = Refund.objects.filter(status="COMPLETED",return_request__order_item__order__in=today_orders,).aggregate(amount=Sum("amount"))["amount"] or Decimal("0.00")

    #build the dashboard's recent-activity and inventory sections
    recent_orders = Order.objects.select_related("user").order_by("-created_at")[:7]

    pending_returns = Return.objects.filter(status__in=["REQUESTED", "PICKED"]).count()

    pending_refunds = Refund.objects.filter(status="PENDING").count()
    low_stock_products = Product.objects.filter(is_active=True,stock_quantity__lte=F("low_stock_threshold"))


    #get best sellers and their images without per-product queries
    best_sellers = list(
        OrderItem.objects.filter(order__payment_status="PAID")
        .exclude(order__status="CANCELLED")
        .exclude(item_status="CANCELLED")
        .values("product_id", "product_name")
        .annotate(units_sold=Sum("quantity"))
        .order_by("-units_sold")
    )

    product_ids = [item["product_id"] for item in best_sellers]

    images = (
        ProductImage.objects.filter(
            Q(product_id__in=product_ids)
            | Q(product_variant__product_id__in=product_ids)
        )
        .select_related("product_variant")
        .order_by("-is_primary", "sort_order", "id")
    )

    #attach the first available image URL to each best seller
    image_urls = {}
    for image in images:
        product_id = (
            image.product_id
            if image.product_id
            else image.product_variant.product_id
        )
        if product_id not in image_urls and image.image_url:
            image_urls[product_id] = image.image_url.url

    for item in best_sellers:
        item["image_url"] = image_urls.get(item["product_id"])


    best_selling_categories = (
        OrderItem.objects.filter(
            order__payment_status="PAID",
            product__isnull=False,
        )
        .exclude(order__status="CANCELLED")
        .exclude(item_status="CANCELLED")
        .values(
            "product__category_id",
            "product__category__name",
        )
        .annotate(units_sold=Sum("quantity"))
        .order_by("-units_sold")[:10]
    )

    context ={
        "total_revenue": net_revenue,
        "total_orders": paid_orders.count(),
        "total_customers": User.objects.filter(is_active=True,is_staff=False,).count(),
        "total_products" : Product.objects.filter(is_active=True).count(),
        "today_orders_count": today_orders.count(),
        "today_revenue": today_sales - today_refunds,
        "average_order_value": (
            net_revenue / paid_orders.count()
            if paid_orders.exists()
            else Decimal("0.00")),
        "recent_orders": recent_orders,
        "pending_returns_count": pending_returns,
        "pending_refunds_count": pending_refunds,
        "low_stock_count": low_stock_products.count(),
        "low_stock_products": low_stock_products,
        "best_sellers": best_sellers,
        "best_selling_categories": best_selling_categories,
        "chart_data": chart_data,
        "chart_period": chart_period,
    }

    return render(request,"adminpanel/admin_dashboard.html",context)