import json

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import never_cache
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import render

from users.models import User

from ..decorators import admin_required


@never_cache
@admin_required
def admin_users_page(request):

    #Get the search text from the URL
    search = request.GET.get("search", "").strip()

    #Get all users except admin
    users = User.objects.filter(is_staff=False)

    #Filter users by name/email
    if search:
        users = users.filter(Q(full_name__icontains=search) | Q(email__icontains=search))
        
    #Show newest users first
    users = users.order_by("-created_at")

    # Divide users into pages
    paginator = Paginator(users, 5)

    #Get requested page
    page_number = request.GET.get("page")

    #Get the users for that page
    users = paginator.get_page(page_number)

    return render(request, "adminpanel/admin_users.html", {"users" : users})


@require_POST
@csrf_exempt
@csrf_exempt
def toggle_user_status(request, user_id):
    # Find the user need to block/unblock
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error" : "User not found"}, status=400)
    # If the user is currently active, block them
    if user.is_active:
        data = json.loads(request.body or "{}")
        # Get the blocking reason sent by the frontend
        block_reason = data.get("reason", "").strip()

        if not block_reason:
            return JsonResponse({"error": "Blocking reason is required"}, status=400)

        user.is_active=False
        user.block_reason = block_reason
        user.blocked_at = timezone.now()


    # If the user is currently blocked, unblock them    
    else:
        user.is_active=True

        # Clear the previous blocking information
        user.block_reason = None
        user.blocked_at=None

    user.save()

    # Return the current status
    status = "active" if user.is_active else "blocked"

    return JsonResponse({"message" : f"User {status} successfully", "status":status},status=200)

