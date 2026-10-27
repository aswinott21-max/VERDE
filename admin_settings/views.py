import json
from datetime import datetime
from django.utils import timezone
from django.contrib import messages
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import redirect,render
from adminpanel.decorators import admin_required
from django.views.decorators.http import require_POST

from users.models import User
from users.services.validation_service import (validate_user_name,validate_user_phone,validate_user_email,validate_user_password)
from users.services.otp_service import (generate_otp,get_otp_expiry,send_otp_email,)



def get_json_data(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    if not isinstance(data, dict):
        return None

    return data

def is_otp_request_limited(user_id, purpose):
    # Create a separate request counter for each admin and OTP purpose.
    cache_key = f"admin_otp_requests:{purpose}:{user_id}"
    requests = cache.get(cache_key, 0)

    # Block requests after 3 successful OTP sends within 10 minutes.
    if requests >= 3:
        return True

    # Allow this request; increment only after the email is sent successfully.
    return False


def record_otp_request(user_id, purpose):
    # Increase the counter after the OTP email is sent successfully.
    cache_key = f"admin_otp_requests:{purpose}:{user_id}"
    requests = cache.get(cache_key, 0)
    cache.set(cache_key, requests + 1, timeout=600)



@admin_required
def admin_settings_page(request):
    return render(request, "admin_settings/admin_settings.html")

@admin_required
@require_POST
def update_admin_profile(request):
    #update prof info
    user = request.user
    full_name = request.POST.get("full_name", "").strip()
    phone = request.POST.get("phone", "").strip()
    profile_picture = request.FILES.get("profile_picture")

    if not full_name or not validate_user_name(full_name):
        messages.error(request,"Please enter a valid fullname")
        return redirect("admin_settings:admin_settings")

    if phone and not validate_user_phone(phone):
        messages.error(request, "Phone number must contain exactly 10 digits")
        return redirect ("admin_settings:admin_settings")

    if phone and User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
        messages.error(request, "That phone number is already in use.")
        return redirect("admin_settings:admin_settings")

    user.full_name = full_name
    user.phone = phone or None

    if profile_picture:
        user.profile_picture = profile_picture

    user.save()
    messages.success(request,"Profile updated successfully.")
    return redirect("admin_settings:admin_settings")


@admin_required
@require_POST
def request_admin_email_change(request):
    data = get_json_data(request)

    # Block requests after 3 successful OTP sends within 10 minutes.
    if is_otp_request_limited(request.user.pk, "email_change"):
        return JsonResponse(
            {"error": "Too many OTP requests. Please try again in 10 minutes."},
            status=429,
        )

    if data is None:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    new_email = data.get("email", "")

    if not isinstance(new_email, str):
        return JsonResponse({"error": "Email must be a string"}, status=400)

    new_email = new_email.strip().lower()

    if not new_email or not validate_user_email(new_email):
        return JsonResponse({"error":"Please enter a valid email address"}, status=400)

    if User.objects.filter(email=new_email).exclude(pk=request.user.pk).exists():
        return JsonResponse({"error":"Email is already in use"}, status=400)

    otp = generate_otp()
    expires_at = get_otp_expiry()

    try:
        send_otp_email(new_email, otp, "email_change")

        # Count the request only after the email is sent successfully.
        record_otp_request(request.user.pk, "email_change")

    except Exception:
        return JsonResponse({"error": "Unable to send OTP. Please try again"},status=500,)

    request.session["admin_settings_email_change_data"] = {
        "user_id": request.user.pk,
        "email": new_email,
        "otp": str(otp),
        "expires_at": expires_at.isoformat(),
    }

    return JsonResponse({"message":"OTP sent to the new email address"}, status=200)


@admin_required
@require_POST
def verify_admin_email_change(request):
    data = get_json_data(request)

    if data is None:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    otp = data.get("otp", "")

    if not isinstance(otp, (str, int)):
        return JsonResponse({"error": "OTP must be a string or number"}, status=400)

    otp = str(otp).strip()

    if not otp:
        return JsonResponse({"error": "OTP is required"}, status=400)

    email_data = request.session.get("admin_settings_email_change_data")

    if not email_data or email_data.get("user_id") != request.user.pk:
        request.session.pop("admin_settings_email_change_data", None)
        return JsonResponse({"error": "No valid email change request. Please request a new OTP."},status=400,)

    expires_at = datetime.fromisoformat(email_data["expires_at"])

    if timezone.now() > expires_at:
        request.session.pop("admin_settings_email_change_data", None)
        return JsonResponse({"error": "OTP has expired. Please request a new OTP."}, status=400)

    if otp != email_data["otp"]:
        attempts = email_data.get("attempts", 0) + 1

        if attempts >= 5:
            request.session.pop("admin_settings_email_change_data", None)
            return JsonResponse(
                {"error": "Too many incorrect OTP attempts. Please request a new OTP."},
                status=400,
            )

        email_data["attempts"] = attempts
        request.session["admin_settings_email_change_data"] = email_data

        return JsonResponse({"error": "Invalid OTP"}, status=400)

    new_email = email_data["email"]

    # Recheck uniqueness before saving.
    if User.objects.filter(email=new_email).exclude(pk=request.user.pk).exists():
        request.session.pop("admin_settings_email_change_data", None)
        return JsonResponse({"error": "Email is already in use"}, status=400)

    user = request.user
    user.email = new_email
    user.save()

    request.session.pop("admin_settings_email_change_data", None)

    return JsonResponse({"message": "Email changed successfully"}, status=200)



@admin_required
@require_POST
def send_admin_password_change_otp(request):
    user = request.user

    # Block requests after 3 successful OTP sends within 10 minutes.
    if is_otp_request_limited(user.pk, "password_change"):
        return JsonResponse(
            {"error": "Too many OTP requests. Please try again in 10 minutes."},
            status=429,
        )

    otp = generate_otp()
    expires_at = get_otp_expiry()

    # Clear any previous verification before issuing a new OTP.
    request.session.pop("admin_settings_password_change_verified", None)

    try:
        send_otp_email(user.email, otp, "password_change")
        # Count the request only after the email is sent successfully.
        record_otp_request(user.pk, "password_change")

    except Exception:
        return JsonResponse(
            {"error": "Unable to send OTP. Please try again."},status=500,)

    request.session["admin_settings_password_change_data"] = {
        "user_id": user.pk,
        "otp": str(otp),
        "expires_at": expires_at.isoformat(),
    }

    return JsonResponse(
        {"message": "Password change OTP sent to your registered email"},
        status=200,
    )


@admin_required
@require_POST
def verify_admin_password_change_otp(request):
    data = get_json_data(request)
    if data is None:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    # Reject unexpected OTP value types.
    otp = data.get("otp", "")

    if not isinstance(otp, (str, int)):
        return JsonResponse({"error": "OTP must be a string or number"}, status=400)

    otp = str(otp).strip()

    if not otp:
        return JsonResponse({"error": "OTP is required"}, status=400)

    change_data = request.session.get("admin_settings_password_change_data")

    if not change_data or change_data.get("user_id") != request.user.pk:
        return JsonResponse(
            {"error": "No valid password change request. Please request a new OTP."},
            status=400,
        )

    expires_at = datetime.fromisoformat(change_data["expires_at"])

    if timezone.now() > expires_at:
        request.session.pop("admin_settings_password_change_data", None)
        request.session.pop("admin_settings_password_change_verified", None)
        return JsonResponse(
            {"error": "OTP has expired. Please request a new OTP."},
            status=400,
        )

    if otp != str(change_data["otp"]):
        attempts = change_data.get("attempts", 0) + 1

        if attempts >= 5:
            request.session.pop("admin_settings_password_change_data", None)
            request.session.pop("admin_settings_password_change_verified", None)
            return JsonResponse(
                {"error": "Too many incorrect OTP attempts. Please request a new OTP."},
                status=400,
            )

        change_data["attempts"] = attempts
        request.session["admin_settings_password_change_data"] = change_data

        return JsonResponse({"error": "Invalid OTP"}, status=400)

    request.session["admin_settings_password_change_verified"] = True

    return JsonResponse({"message": "OTP verified successfully"}, status=200)


@admin_required
@require_POST
def change_admin_password(request):
    # Reject invalid JSON or JSON that isn't an object.
    data = get_json_data(request)

    if data is None:
        return JsonResponse({"error": "Invalid JSON data"}, status=400)

    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")
    # Password fields must be strings.
    if not isinstance(password, str) or not isinstance(confirm_password, str):
        return JsonResponse(
            {"error": "Password fields must be strings"},
            status=400,
        )

    if not password or not confirm_password:
        return JsonResponse(
            {"error": "Both password fields are required"},
            status=400,
        )

    if password != confirm_password:
        return JsonResponse({"error": "Passwords do not match"}, status=400)

    if not validate_user_password(password):
        return JsonResponse(
            {
                "error": (
                    "Password must contain at least 8 characters, "
                    "one uppercase letter, one lowercase letter, "
                    "one number, and one special character."
                )
            },
            status=400,
        )

    change_data = request.session.get("admin_settings_password_change_data")

    if (
        not request.session.get("admin_settings_password_change_verified")
        or not change_data
        or change_data.get("user_id") != request.user.pk
    ):
        return JsonResponse(
            {"error": "Please verify the OTP first"},
            status=403,
        )

    # Do not allow a previously verified but expired OTP.
    expires_at = datetime.fromisoformat(change_data["expires_at"])
    if timezone.now() > expires_at:
        request.session.pop("admin_settings_password_change_data", None)
        request.session.pop("admin_settings_password_change_verified", None)
        return JsonResponse(
            {"error": "OTP has expired. Please request a new OTP."},
            status=400,
        )

    user = request.user
    user.set_password(password)
    user.save()
    # Keep the admin logged in after changing their password.
    from django.contrib.auth import update_session_auth_hash
    update_session_auth_hash(request, user)

    request.session.pop("admin_settings_password_change_data", None)
    request.session.pop("admin_settings_password_change_verified", None)

    return JsonResponse({"message": "Password changed successfully"}, status=200)
