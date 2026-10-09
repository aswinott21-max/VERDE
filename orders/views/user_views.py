import logging
import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from datetime import timedelta

from orders.services.order_service import (cancel_order,return_order,cancel_order_item,return_order_item)
from orders.services.invoice_service import generate_invoice_pdf

from orders.models import Order


logger = logging.getLogger(__name__)

@login_required
def order_list(request):

    search = request.GET.get("search","").strip()


    orders = (Order.objects.filter(user=request.user).order_by("-created_at"))

    if search:
        orders = orders.filter(Q(order_number__icontains=search) | Q(items__product_name__icontains=search)).distinct()

    page_number = request.GET.get("page")
    paginator = Paginator(orders,5)
    page_obj = paginator.get_page(page_number)


    logger.info("Order list opened by user: %s | Search: %s | Orders : %s", request.user,search,orders.count(),)

    all_orders_count = Order.objects.filter(user=request.user).count()
    processing_count = Order.objects.filter(user=request.user,status__in =["PLACED","PROCESSING","SHIPPED","OUT_FOR_DELIVERY"]).count()
    delivered_count = Order.objects.filter(user=request.user,status="DELIVERED").count()
    returned_count = Order.objects.filter(user=request.user,status="RETURNED",).count()
    print("ORDERS:", list(orders.values("order_number", "status", "created_at")))

    cancellable_statuses =  ["PLACED","PROCESSING","SHIPPED", "OUT_FOR_DELIVERY"]

    returnable_statuses = ["DELIVERED"]

    return render (request,"orders/order_list.html",{"orders":page_obj,"page_obj":page_obj, "all_orders_count" :all_orders_count,"processing_count":processing_count,"delivered_count":delivered_count,"returned_count" : returned_count,"cancellable_statuses":cancellable_statuses,"returnable_statuses": returnable_statuses,})

@login_required
def order_detail(request,order_number):

    #order of logged in user
    order = (Order.objects.filter(order_number=order_number,user=request.user).prefetch_related("items","status_history",).select_related("address").first())

    if not order:
        logger.warning("Order not found: %s | User: %s",order_number,request.user)

        return render(request,"orders/order_not_found.html",status=404,)
    logger.info("Order details opened: %s | User:%s",order.order_number,request.user)

    estimated_delivery_start = order.created_at + timedelta(days=3)
    estimated_delivery_end = order.created_at + timedelta(days=4)

    return render(request, "orders/order_detail.html",{"order" : order,"estimated_delivery_start":estimated_delivery_start,"estimated_delivery_end": estimated_delivery_end},)

@login_required
def download_invoice(request, order_number):
    order = (Order.objects.filter(order_number = order_number, user=request.user,).prefetch_related("items").select_related("address").first())
    if not order:
        return render(request, "order/order_not_found.html",status=404)
    return generate_invoice_pdf(order)

@login_required
@require_POST
def cancel_order_api(request, order_number):
    data = json.loads(request.body or "{}")
    cancellation_reason = data.get("cancellation_reason", "").strip()
    order, error = cancel_order(user=request.user,order_number=order_number,cancellation_reason=cancellation_reason or None)

    if error:
        return JsonResponse({"message":error}, status=400)
    logger.info("Order cancelled successfully: %s | User : %s", order_number,request.user,)

    return JsonResponse({
        "message": "Order cancelled successfully.",
        "order_number": order.order_number,
    }, status=200)


@login_required
@require_POST
def return_order_api(request, order_number):
    data = json.loads(request.body or "{}")

    return_reason= data.get("return_reason", "").strip()
    order,error = return_order(user=request.user, order_number=order_number, return_reason=return_reason)

    if error:
        return JsonResponse({"message":error},status=400)

    logger.info("Return requested successfully: %s | User: %s",order_number,request.user)

    return JsonResponse({
        "message": "Return request submitted successfully.",
        "order_number": order.order_number,
    }, status=200,)

@login_required
@require_POST
def return_order_item_api(request,order_number, order_item_id):

    data = json.loads(request.body or "{}")

    return_reason = data.get("return_reason", "").strip()
    user_add_note = data.get("user_add_note", "").strip()

    return_request,error = return_order_item(user=request.user, order_number=order_number,order_item_id= order_item_id,return_reason=return_reason,user_add_note=user_add_note)

    if error:
        return JsonResponse({"message": error}, status=400)

    logger.info("Iter return requested successfully: %s | Item: %s | User: %s",order_number,order_item_id,request.user,)

    return JsonResponse(
        {
            "message": "Item return request submitted successfully.",
            "order_number": order_number,
            "order_item_id": order_item_id, 
        },status=200)

@login_required
@require_POST
def cancel_order_item_api(request,order_number,order_item_id):
    data= json.loads(request.body or "{}")
    cancellation_reason=data.get("cancellation_reason","").strip()

    order_item,error = cancel_order_item(user=request.user,order_number=order_number,order_item_id=order_item_id,cancellation_reason=cancellation_reason or None,)

    if error:
        return JsonResponse({"message":error}, status=400)

    logger.info("Order item cancelled successfully: %s | Order: %s | User: %s",order_item_id,order_number,request.user,)

    return JsonResponse({
        "message": "Order item cancelled successfully.",
        "order_number": order_number,
        "order_item_id": order_item.id,
    }, status=200)