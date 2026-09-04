import json
from .models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .services.validation_service import(validate_user_email,validate_user_phone,validate_user_password,is_phone_taken,is_email_taken)
from .services.otp_service import generate_otp, get_otp_expiry, send_otp_email
from datetime import datetime
from django.utils import timezone
from django.shortcuts import render
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from .services.auth_service import hash_user_password


@csrf_exempt
@require_POST
def signup(request):
    data = json.loads(request.body)

    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")
    confirm_password = data.get("confirm_password")

    #Check required fields
    if not name or not email or not phone or not password or not confirm_password:
        return JsonResponse({
            "error" : "All fields are required"
        },status=400)

    #Email validation
    if not validate_user_email(email):
        return JsonResponse({
            "error" : "Enter a valid email address"
        }, status=400)
   

    #Phone validation
    if not validate_user_phone(phone):
        return JsonResponse({
            "error" : "Phone number must contain exactly 10 digits"
        }, status=400)
  
    

    #Check email and phone already exist
    if is_email_taken(email,User):
        return JsonResponse({
            "error" : "Email already exists"
        }, status=400)

    if is_phone_taken(phone, User):
        return JsonResponse({
            "error": "phone number already exists"
    }, status=400)

    #Password validation
    if not validate_user_password(password):
        return JsonResponse({
            "error": "Password must contain at least 8 charecters, one uppercase, one lowercase, one number, and one special character"
        }, status=400)

  
    #Check password confirmation
    if password != confirm_password:
        return JsonResponse({
            "error" : "Passwords do not match"
        }, status = 400)

    #Generate OTP
    otp = generate_otp()

    send_otp_email(email, otp, "signup")
  
    #OTP expires after 5 minutes
    otp_expires_at = get_otp_expiry()

    #Store signup data temporarily
    request.session["signup_data"]={
        "name": name,
        "email": email,
        "phone": phone,
        "password": hash_user_password(password), #Hash password using the authentication service
        "otp": otp,
        "otp_expires_at" : otp_expires_at.isoformat(),
        #isoformat() - django canot directly store a python datetime object in the  normal JSON session serializer

    }
    

    return JsonResponse({
        "message" : "OTP generated successfully"
    })


@csrf_exempt
@require_POST
def verify_otp(request):
    data = json.loads(request.body)

    otp = data.get("otp")

    if not otp:
        return JsonResponse({
            "error" : "OTP is required"
        }, status=400)

    signup_data = request.session.get("signup_data")

    if not signup_data:
        return JsonResponse({
            "error" : "Signup session expired. Please signup again."
        }, status=400)

    otp_expires_at = datetime.fromisoformat(
        signup_data["otp_expires_at"]
    )

    if timezone.now()> otp_expires_at:
        return JsonResponse({
             "error": "OTP has expired. Please request a new OTP."
        },status = 400)

    if str(otp) != str(signup_data["otp"]):
        return JsonResponse({
            "error" : "Invalid OTP"
        }, status=400)

    #marking email as verified
    request.session["email_verified"] = True

    #remove the OTP
    signup_data.pop("otp",None)
    #Save the updated signup
    request.session["signup_data"] = signup_data

    return JsonResponse({
        "message" : "Email verified successfully"
    })


@csrf_exempt
@require_POST
def resend_otp(request):

    signup_data = request.session.get("signup_data")



    #Check signup session
    if not signup_data:
        return JsonResponse({
            "error" : "Signup session expired. Please signup again"
        }, status=400)
    #Generate new OTP
    otp = generate_otp()

    
    send_otp_email(signup_data["email"], otp, "resend")
    

    #Reset expiry to 5 minute
    otp_expires_at = get_otp_expiry()

    #Update OTP and expiry
    signup_data["otp"] = otp
    signup_data["otp_expires_at"] = otp_expires_at.isoformat()

    #Save updated data back to session
    request.session["signup_data"] = signup_data

    

    return JsonResponse({
        "message" : "New OTP generate successfully"
    })



@csrf_exempt
@require_POST
def create_account(request):

    signup_data = request.session.get("signup_data")
    email_verified = request.session.get("email_verified")

    #Check signup session
    if not signup_data:
        return JsonResponse({
            "error" : "Signup session expired. Please signup again."
        }, status=400)

    #Check email verification
    if not email_verified:
        return JsonResponse({
            "error" : "Please verify your email first"
        }, status=400)

    #Create user
    user = User(
        email=signup_data["email"],
        full_name = signup_data["name"],
        phone = signup_data["phone"],
        password = signup_data["password"]
       )

    # Mark email as verified
    user. is_verified = True
    user.save()

    #Clear signup data from session
    request.session.pop("signup_data", None)
    request.session.pop("email_verified", None)

    return JsonResponse({
        "message" : "Account created successfully",
        "email" : user.email
    }, status=201)

def signup_page(request):
    return render(request, "users/signup.html")

def verify_otp_page(request):
    return render(request, "users/verify_otp.html")

def login_page(request): # load login page
    return render(request, "users/login.html")

#Login API
@csrf_exempt
@require_POST
def login(request): # to process login credentials
    data = json.loads(request.body) # reading login data send front end

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return JsonResponse({
            "error" : "Email and password are required"
        }, status = 400)

    try:
        user= User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({
            "error" : "Invalid email or password"
        }, status=401)

    if not user.is_verified:
            return JsonResponse({
                "error" : "Please verify your email first"
            }, status=403)

    if not user.check_password(password):
        return JsonResponse({
            "error" : "Invalid email or password"
        }, status=401)


    auth_login(request, user)

    return JsonResponse({
        "message" : "Login successful",
        "email" : user.email

    },status=200)

@login_required
def dashboard_page(request):
    return render(request, "users/dashboard.html")

# Logout API
@csrf_exempt
@require_POST
def logout(request):
    request.session.flush()

    return JsonResponse({
        "message" : "Logout successful"
    }, status=200)

def forgot_password_page(request):
    return render(request, "users/forgot_password.html")

@csrf_exempt
@require_POST
def forgot_password(request): #API

    data = json.loads(request.body)

    email = data.get("email")

    if not email: 
        return JsonResponse({
            "error" : "Email is required"
        }, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({
            "error" : "Email does not exists"
        }, status=404)
    if not user.is_verified:
        return JsonResponse({
            "error" : "Please verify your email first"
        }, status=403)

    otp = generate_otp()

    otp_expires_at = get_otp_expiry()
    #Store the password reset data in the user's session
    request.session["password_reset_data"] ={
        "email" : user.email,
        "otp" : otp,
        "otp_expires_at" : otp_expires_at.isoformat(),
    }
    # Send the OTP to the user's email
    send_otp_email(user.email, otp, "password_reset")

    return JsonResponse({
        "message": "OTP generated successfully"
    }, status=200)

#Reset password OTP page 
def reset_password_otp_page(request):
    return render(request, "users/reset_password_otp.html")

@csrf_exempt
@require_POST
def verify_reset_password_otp(request):
    #Read the OTP sent from the frontend
    data = json.loads(request.body)

    otp =data.get("otp")

    if not otp:
        return JsonResponse({
            "error" : "OTP is required"
        }, status=400)

    reset_data = request.session.get("password_reset_data")

    #Check whether the reset session exists
    if not reset_data:
        return JsonResponse({
            "error": "Password reset session expired. Please try again."
        }, status=400)

    # Convert the stored expiry time back to a datetime
    otp_expires_at = datetime.fromisoformat(
        reset_data["otp_expires_at"]
    )

    # Check whether the OTP has expired
    if  timezone.now() > otp_expires_at:
        return JsonResponse({
            "error" : "OTP has expired. Please request a new OTP."
        }, status=400)

    # Check whether the entered OTP matches the stored OTP
    if  str(otp) != str(reset_data["otp"]): 
        return JsonResponse({
            "error" : "Invalid OTP"
        }, status=400)

    request.session["password_reset_verified"]=True

    return JsonResponse({
        "message":"OTP verified successfully"
    }, status=200)

def reset_password_page(request):
    return render(request, "users/reset_password.html")


# Reset the user's password API
@csrf_exempt
@require_POST
def reset_password(request):
    data = json.loads(request.body)
    print("Reset Password Data:", data)

    password = data.get("password")
    confirm_password = data.get("confirm_password")

    if not password or not confirm_password:
        return JsonResponse({
            "error" : "Both password fields are required"
        }, status=400)

    if password != confirm_password:
        return JsonResponse({
            "error" : "Password do not match"
        }, status=400)

    if not request.session.get("password_reset_verified"):
        # Temporary debugging: check whether OTP verification was completed
        print("Password Reset Verified:", request.session.get("password_reset_verified"))
        return JsonResponse({
            "error" : "Please verify the OTP first"
        }, status=403)

    #Get data (password reset) from session
    reset_data = request.session.get("password_reset_data")

    if not reset_data:
        return JsonResponse({
            "error" : "Password reset session expired. Please try again."
        }, status=400)

    # Find the user using the email stored in the reset session
    try:
        user = User.objects.get(email=reset_data["email"])
    except User.DoesNotExist:
        return JsonResponse({
            "error" : "User not found"
        },status=404)

    # Hash the new password and save it to the database
    user.set_password(password)
    user.save()

    # Remove password reset data after successful password change
    request.session.pop("password_reset_data", None)
    request.session.pop("password_reset_verified", None)

    return JsonResponse({
        "message" : "Password reset successfully"
    }, status=200)
    

    

    


