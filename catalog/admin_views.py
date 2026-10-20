from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.views.decorators.cache import never_cache
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from decimal import Decimal, InvalidOperation

from .models import Category

from adminpanel.decorators import admin_required

#Services
from .services.category_validation import validate_category_data



@never_cache
@admin_required
def category_dashboard(request):

    # get the search text from the request
    search = request.GET.get("search", "").strip()

    #to get all category
    categories = Category.objects.filter(parent__isnull=False).select_related("parent").annotate(product_count=Count("products")).order_by("-created_at")

    if search:
        categories = categories.filter(name__icontains=search)

    paginator = Paginator(categories, 5)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    # Get only top-level categories for the parent dropdown
    parent_categories = Category.objects.filter(parent__isnull=True,is_active=True).order_by("name")

    #returning category and search values    
    return render(request, "adminpanel/admin_cat_dashboard.html",{"categories":page_obj,"page_obj": page_obj,"search":search,"parent_categories": parent_categories,})

@require_POST
@admin_required
def add_category(request):
    #get category data from the request
    name = request.POST.get("name")
    description = request.POST.get("description")
    parent_id = request.POST.get("parent_id")

    #validate required field
    error = validate_category_data(name or "", description or "")
    if error:
        return JsonResponse({
            "success": False,
            "message": error,
        }, status=400)


    # If a parent category was selected, make sure it exists
    parent = None

    if parent_id:
        #Only top-level categories can be selected as parents.
        parent = get_object_or_404(Category,id=parent_id, parent__isnull=True)


    #create catg
    category = Category.objects.create(name=name,description=description, parent=parent)
    

    return JsonResponse({
        "success":True, 
        "message":"Category created successfully.",
        "data":{
            "id":category.id,
            "name": category.name,
            "description": category.description,
            "parent_id" : category.parent_id
            }
        }, status=201)

@admin_required
def edit_category(request, category_id):

    if request.method != "POST":
        return JsonResponse({"success":False,"message":"Only POST requests are allowed."}, status=405)

    # Find the category or return 404 if it doesn't exist
    category = get_object_or_404(Category, id=category_id)

    name = request.POST.get("name")
    description= request.POST.get("description")
    parent_id = request.POST.get("parent_id")

    #Validate
    error = validate_category_data(name or "", description or "")

    if error:
        return JsonResponse({"success": False,"message": error, "data":None}, status=400)

    # Default: no parent
    parent = None

    # Find the selected parent category
    if parent_id:
        if int(parent_id)==category.id:
            return JsonResponse({"success": False,"message": "A category cannot be its own parent.","data": None}, status=400)
        parent = get_object_or_404(Category, id=parent_id, parent__isnull=True)

    #Update category
    category.name = name
    category.description = description
    category.parent = parent

    category.save()

    return JsonResponse({
        "success": True,
        "message": "Category updated successfully.",
        "data": {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "parent_id" : category.parent_id
        }
    })


@admin_required
def toggle_category_status(request, category_id):
    if request.method != "POST":
        return JsonResponse({"success":False, "message":"Only POST request are allowed."}, status=405)

    #Find cantegory
    category = get_object_or_404(Category, id=category_id)

    # Toggle the active status
    category.is_active = not category.is_active
    category.save()

    #Return the new status
    status ="Listed" if category.is_active else "unlisted"

    return JsonResponse({"success":True,"message": f"Category {status} successfully.",
                         "data":{
                            "id":category.id,
                            "is_active":category.is_active}
                        })


@admin_required
def set_category_offer(request, category_id):
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "message": "Only POST requests are allowed."},status=405,)

    category = get_object_or_404(Category, id=category_id)

    if request.POST.get("remove_offer") == "true":
        category.discount_value = 0
        category.offer_start_at = None
        category.offer_end_at = None
        category.save()

        return JsonResponse({
            "success": True,
            "message": "Offer removed successfully.",
            "data": {"category_id": category.id},
        })

    discount_raw = request.POST.get("discount_value", "").strip()
    start_raw = request.POST.get("offer_start_at", "").strip()
    end_raw = request.POST.get("offer_end_at", "").strip()

    if not discount_raw:
        return JsonResponse(
            {"success": False, "message": "Discount value is required."},
            status=400,
        )
    if not start_raw:
        return JsonResponse(
            {"success": False, "message": "Start date and time are required."},
            status=400,
        )
    if not end_raw:
        return JsonResponse(
            {"success": False, "message": "End date and time are required."},
            status=400,
        )

    try:
        discount_value = Decimal(discount_raw)
    except (InvalidOperation, ValueError):
        return JsonResponse(
            {"success": False, "message": "Enter a valid discount."},status=400,)

    if not discount_value.is_finite() or not Decimal("0") <= discount_value <= Decimal("100"):
        return JsonResponse(
            {"success": False, "message": "Discount must be between 0 and 100."},status=400,)

    offer_start_at = parse_datetime(start_raw)
    offer_end_at = parse_datetime(end_raw)

    if start_raw and offer_start_at is None:
        return JsonResponse(
            {"success": False, "message": "Enter a valid start date and time."},
            status=400,
        )

    if end_raw and offer_end_at is None:
        return JsonResponse(
            {"success": False, "message": "Enter a valid end date and time."},
            status=400,
        )

    if offer_start_at and timezone.is_naive(offer_start_at):
        offer_start_at = timezone.make_aware(offer_start_at)

    if offer_end_at and timezone.is_naive(offer_end_at):
        offer_end_at = timezone.make_aware(offer_end_at)

    now = timezone.now()

    if offer_start_at and offer_start_at < now:
        return JsonResponse({"success": False, "message": "Offer start cannot be in the past."},status=400,)

    if offer_start_at and offer_end_at and offer_end_at < offer_start_at:
        return JsonResponse({"success": False, "message": "Offer end must be after the start."},status=400,)

    category.discount_value = discount_value
    category.offer_start_at = offer_start_at
    category.offer_end_at = offer_end_at
    category.save()

    return JsonResponse({
        "success": True,
        "message": "Offer applied successfully.",
        "data": {
            "category_id": category.id,
            "discount_value": str(discount_value),
            "offer_start_at": start_raw,
            "offer_end_at": end_raw,
        },
    })