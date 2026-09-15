import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from users.models import User, Address
from django.contrib.auth import login as auth_login
from datetime import datetime
from django.utils import timezone
from django.shortcuts import render, redirect
from django.core.paginator import Paginator

# User authentication and validation services
from users.services.otp_service import (generate_otp,get_otp_expiry,send_otp_email,)
from users.services.validation_service import validate_user_password



# Create your views here.


def admin_login_page(request):
    return render(request, "adminpanel/admin_login.html")


@csrf_exempt
@require_POST
def admin_login(request): #API
    data = json.loads(request.body)

    email =data.get("email")
    password = data.get("password")

    if not email or not password:
        return JsonResponse({
            "error" : "Email and password are required"
        }, status=400)

    try:
        user =User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({
            "error" : "Invalid email or password"
        }, status=401)

    if not user.is_staff:
        return JsonResponse({
            "error" : "You are not authorized as an admin"
        }, status=403)

    if not user.check_password(password):
        return JsonResponse({
            "error" : "Invalid email or password"
        }, status=401)

    #Create the Django Login session
    auth_login(request, user)

    return JsonResponse({
        "message" : "Admin login successful",
        "email" : user.email
    }, status=200)


@csrf_exempt
@require_POST
def admin_forgot_password(request):
    # Read the email sent from the admin login page
    data = json.loads(request.body)
    email = data.get("email")

    if not email:
        return JsonResponse({"error" : "Email is required"}, status=400)

    # Find the account using the entered email
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"error" : "Invalid admin email"}, status= 404)

    # Only admin accounts can use this reset flow

    if not user.is_staff:
        return JsonResponse({"error" : "You are not a authorised as an admin"}, status=403)

    # Generate a new OTP
    otp = generate_otp()
    otp_expires_at = get_otp_expiry()

    # Store in session
    request.session["admin_password_reset_data"]={
        "email" : user.email,
        "otp" : otp,
        "otp_expires_at": otp_expires_at.isoformat(),
    }

    #Send OTP to admin amil
    send_otp_email(user.email, otp, "password_reset")

    return JsonResponse({"message" : "Admin password reset OTP sent successfully"}, status=200)



@csrf_exempt
@require_POST
def admin_resend_otp(request):
    # Read the admin email from the request
    data = json.loads(request.body)
    email = data.get("email")

    if not email:
        return JsonResponse({
            "error": "Email is required"
        }, status=400)

    # Find the admin account
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({
            "error": "Invalid admin email"
        }, status=404)

    # Only admin accounts can request a new OTP
    if not user.is_staff:
        return JsonResponse({
            "error": "You are not authorized as an admin"
        }, status=403)

    # Generate a completely new OTP
    otp = generate_otp()
    otp_expires_at = get_otp_expiry()

    # Replace the old OTP with the new OTP
    request.session["admin_password_reset_data"] = {
        "email": user.email,
        "otp": otp,
        "otp_expires_at": otp_expires_at.isoformat(),
    }

    # Send the new OTP to the admin email
    send_otp_email(user.email, otp, "resend")

    return JsonResponse({
        "message": "New admin OTP sent successfully"
    }, status=200)


@csrf_exempt
@require_POST
def verify_admin_reset_password_otp(request):
    # Read the OTP entered by the admin
    data = json.loads(request.body)
    otp = data.get("otp")

    if not otp:
        return JsonResponse({"error":"OTP is required"}, status=400)

    # Get the admin password reset data from the session
    reset_data = request.session.get("admin_password_reset_data")

    if not reset_data:
        return JsonResponse({
            "error" : "Password reset session expired. Please try again."
        }, status=400)

    # Convert the stored expiry time back to a datetime
    otp_expires_at = datetime.fromisoformat( reset_data["otp_expires_at"])

    # Check whether the OTP has expired
    if  timezone.now() > otp_expires_at:
        return JsonResponse({
            "error" : "OTP has expired. PLease requet a new OTP."
        }, status=400)

    #Check otp is correct
    if str(otp) != str(reset_data["otp"]):
        return JsonResponse({"error" : "Invalid OTP"}, status=400)

    # Mark the admin OTP verification as completed
    request.session["admin_password_reset_verified"] = True

    return JsonResponse({"message":"Admin OTP verified succesfully"}, status=200)



@csrf_exempt
@require_POST
def admin_reset_password(request):
    # Read the new password from the frontend
    data = json.loads(request.body)

    password = data.get("password")
    confirm_password = data.get("confirm_password")

    if not password or not confirm_password:
        return JsonResponse({
            "error": "Both password fields are required"
        }, status=400)

    # Check whether both passwords match
    if password != confirm_password:
        return JsonResponse({
            "error": "Passwords do not match"
        }, status=400)

    # Validate the new password
    if not validate_user_password(password):
        return JsonResponse({
            "error": (
                "Password must contain at least 8 characters, "
                "one uppercase letter, one lowercase letter, "
                "one number, and one special character."
            )
        }, status=400)

    # OTP must be verified before changing the password
    if not request.session.get("admin_password_reset_verified"):
        return JsonResponse({
            "error": "Please verify the OTP first"
        }, status=403)

    # Get admin reset data from the session
    reset_data = request.session.get("admin_password_reset_data")

    if not reset_data:
        return JsonResponse({
            "error": "Password reset session expired. Please try again."
        }, status=400)

    # Find the admin account
    try:
        user = User.objects.get(
            email=reset_data["email"],
            is_staff=True
        )
    except User.DoesNotExist:
        return JsonResponse({
            "error": "Admin account not found"
        }, status=404)

    # Save the new password securely
    user.set_password(password)
    user.save()

    # Clear the reset session after successful reset
    request.session.pop("admin_password_reset_data", None)
    request.session.pop("admin_password_reset_verified", None)

    return JsonResponse({
        "message": "Admin password reset successfully"
    }, status=200)

@login_required(login_url="/admin-login/")
def admin_dashboard_page(request):

    if not request.user.is_staff:
        return JsonResponse({
            "error" : "You are not authorize to access admin dashbaoard"
        }, status=403)

    return render(request,"adminpanel/admin_dashboard.html")



@csrf_exempt
@require_POST
def admin_logout(request):
    # Clear the admin's login session
    request.session.flush()

    return redirect("/admin-login/")




@require_POST
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









@login_required(login_url= "/admin-login/")
def admin_users_page(request):

    if not request.user.is_staff:
        return JsonResponse({
            "error" : "You are not authorized to access user manaagement"
        }, status=403)

    #Get the search text from the URL
    search = request.GET.get("search", "").strip()

    #Get all users except admin
    users = User.objects.filter(is_staff=False)

    #Filter users by name/email
    if search:
        users = users.filter(
            full_name__icontains=search
        ) | users.filter(
            email__icontains=search
        )

    #Show newest users first
    users = users.order_by("-created_at")

    # Divide users into pages
    paginator = Paginator(users, 5)

    #Get requested page
    page_number = request.GET.get("page")

    #Get the users for that page
    users = paginator.get_page(page_number)

    return render(request, "adminpanel/admin_users.html", {"users" : users})
