from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q
from django.core.paginator import Paginator
from django.views.decorators.cache import never_cache

from orders.models import Order
from adminpanel.decorators import admin_required
from orders.services.order_service import (update_order_status,update_return_status,update_return_note)
from orders.services.invoice_service import generate_invoice_pdf



@admin_required
@never_cache
def admin_order_list(request):

    search =request.GET.get("search","").strip()
    orders = (Order.objects.select_related("user"))
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search)
            | Q(user__full_name__icontains=search)
            | Q(user__email__icontains=search)
            | Q(user__phone__icontains=search)
        )

    status = request.GET.get("status", "").strip().upper()

    if status:
        orders = orders.filter(status=status)

    sort = request.GET.get("sort", "newest")

    if sort == "oldest":
        orders = orders.order_by("created_at")

    elif sort == "amount_high":
        orders = orders.order_by("-total_amount")

    elif sort == "amount_low":
        orders = orders.order_by("total_amount")

    else:
        orders = orders.order_by("-created_at")

    paginator = Paginator(orders,6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)


    allowed_transitions = {
        "PLACED": ["PROCESSING", "CANCELLED"],
        "PROCESSING": ["SHIPPED", "CANCELLED"],
        "SHIPPED": ["OUT_FOR_DELIVERY", "CANCELLED"],
        "OUT_FOR_DELIVERY": ["DELIVERED", "CANCELLED"],
        "DELIVERED": ["RETURNED"],
        "CANCELLED": [],
        "RETURNED": [],
    }

    return render(request,"orders/admin_order_list.html",{"orders": page_obj,"page_obj":page_obj,"allowed_transitions": allowed_transitions,},)


@admin_required
@never_cache
def admin_order_details(request, order_number):
    order = (Order.objects.select_related("user","address").prefetch_related("items__returns").filter(order_number=order_number).first())
    if not order:
        return render(request, "orders/admin_order_not_found.html",status=404)
    return render(request,"orders/admin_order_detail.html",{"order":order})


@admin_required
@never_cache
def admin_update_order_status(request, order_number):

    if request.method != "POST":
        return JsonResponse({"message":"Status is required"}, status=400,)

    new_status = request.POST.get("status", "").strip().upper()

    if not new_status:
        return JsonResponse({"message": "Status is required."}, status=400)

    order, error = update_order_status(order_number=order_number,new_status=new_status)

    if error:
        return JsonResponse({"message": error}, status=400)

    return JsonResponse({
        "message": "Order status updated successfully.",
        "order_number": order.order_number,
        "status": order.status,
    },status=200)

@admin_required
@never_cache
def admin_update_return_status(request, return_id):

    if request.method != "POST":
        return JsonResponse({"message": "Return status is required"}, status=400)

    new_status = request.POST.get("status", "").strip().upper()

    if not new_status:
        return JsonResponse({"message":"Return status is required"}, status=400)

    return_request, error = update_return_status(return_id=return_id, new_status=new_status,)

    if error:
        return JsonResponse({"message":error},status=400)

    return JsonResponse({
        "message": "Return status updated successfully.",
        "return_id": return_request.id,
        "status": return_request.status,
    },status=200)


@admin_required
@never_cache
def admin_update_return_note(request, return_id):

    if request.method != "POST":
        return JsonResponse({"message": "Internal note is required."}, status=400)

    internal_note = request.POST.get("Internal_note", "").strip()

    return_request, error = update_return_note(return_id=return_id, internal_note=internal_note)

    if error:
        return JsonResponse({"message":error}, status=400)

    return JsonResponse(
        {
            "message": "Internal note updated successfully.",
            "return_id": return_request.id,
        },status=200,)

@admin_required
@never_cache
def admin_download_invoice(request, order_number):
    order = (Order.objects.filter(order_number=order_number).prefetch_related("items").select_related("user", "address").first())
    if not order:
        return render(request,"orders/admin_order_not_found.html",status=404,)

    return generate_invoice_pdf(order)