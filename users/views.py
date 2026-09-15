import json
from users.models import User, Address
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .services.validation_service import(validate_user_email,validate_user_phone,validate_user_name,validate_user_password,is_phone_taken,is_email_taken,validate_pin,validate_address_line,validate_city)
from .services.otp_service import generate_otp, get_otp_expiry, send_otp_email
from datetime import datetime
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from .services.auth_service import hash_user_password
from django.core.paginator import Paginator

#Google OAuth
from authlib.integrations.django_client import OAuth
from django.conf import settings

from django.views.decorators.csrf import ensure_csrf_cookie

#create google OAuth client
oauth = OAuth()

# Register Google OAuth provider
oauth.register(
    name="google",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,

    # Google's OpenID Connect metadata
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
   

    client_kwargs={
        "scope": "openid email profile",
        "token_endpoint_auth_method": "client_secret_post"
    }

)

@csrf_exempt
@require_POST
def signup(request):
    data = json.loads(request.body)

    name = data.get("name", "").strip()
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")
    confirm_password = data.get("confirm_password")



    #Check required fields
    if not name or not email or not phone or not password or not confirm_password:
        return JsonResponse({
            "error" : "All fields are required"
        },status=400)

    #Name validation
    if not validate_user_name(name):
        return JsonResponse({"error" : "Enter a valid full name"}, status=400)

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
  
    #OTP expires after 1 minutes
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
    

    #Reset expiry to 1 minute
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

    password_error = validate_user_password(password)


    if not validate_user_password(password):
        return JsonResponse({"error":"Password must contain at least 8 characters, one uppercase letter, one lowercase letter, one number, and one special character."}, status=400)

    

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
    

    

@login_required
@require_POST
def send_change_password_otp(request):

    user=request.user

    #Generate OTP & Time
    otp = generate_otp()
    otp_expires_at = get_otp_expiry()

    #Store in session
    request.session["change_password_data"]={
        "otp" : otp,
        "otp_expires_at" : otp_expires_at.isoformat(),
    }

    #Send otp to registered mail

    send_otp_email(user.email, otp,"password_change")

    return JsonResponse({"message":"OTP sent successfully"},status=200)


# Verify the OTP for changing password
@login_required
@require_POST
def verify_change_password_otp(request):

    data = json.loads(request.body)
    otp = data.get("otp", "").strip()

    if not otp:
        return JsonResponse({"error":"OTP is required"})

    change_data = request.session.get("change_password_data")

    if not change_data:
        return JsonResponse({"error":"Password change session expired. Please request a new OTP."}, status=400)

    # Convert stored expiry string back to datetime
    otp_expires_at = datetime.fromisoformat(change_data["otp_expires_at"])

    #check expiry
    if timezone.now()> otp_expires_at:
        request.session.pop("change_password_data", None)

        return JsonResponse({"error":"OTP has expired. Please request a new OTP."}, status=400)

    #Check otp
    if str(otp) != str(change_data["otp"]):
        return JsonResponse({ "error" : "Invalid OTP"}, status=400)

    #Mard verified OTP
    request.session["change_password_verified"]=True

    return JsonResponse({"message" : "OTP verified successfully"}, status=200)


# Save the new password
@login_required
@require_POST
def change_password(request):

    data = json.loads(request.body)

    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")

    if not password or not confirm_password:
        return JsonResponse({"error":"Both password field are required"}, status=400)

    if password != confirm_password :
        return JsonResponse({"error" : "Passwords do not match"}, status=400)

    if not validate_user_password(password):
        return JsonResponse({"error" : "Password must contain at least 8 characters, one uppercase letter, one lowercase letter, one number, and one special character."}, status=400)

    # Make sure OTP was verified first
    if not request.session.get("change_password_verified"):
        return JsonResponse({"error":"Please verify the OTP first"}, status=403)

    #Set the new password
    user = request.user
    user.set_password(password)
    user.save()

    # Clear password-change session data
    request.session.pop("change_password_data", None)
    request.session.pop("change_password_verified", None)
    return JsonResponse({"message" : "Password changed succefully"},status=200)

    

def home_page(request):

    return render (request, "users/home.html")


def google_login(request):
    #redirect the user to google's login page
    redirect_uri = request.build_absolute_uri("/google/callback/")

    return oauth.google.authorize_redirect(request, redirect_uri)

def google_callback(request):
    #get authorize code from google
    token = oauth.google.authorize_access_token(request)

    #get user google profile information
    user_info = token.get("userinfo")

    if not user_info:
        return JsonResponse({"error":"Google authentication failed"}, status=400 )

    #get user email and name from google
    email = user_info.get("email")
    full_name = user_info.get("name", "")

    # check already a verde user
    user =User.objects.filter(email=email).first()

    if not user:

        user = User.objects.create_user(
            email=email,
            full_name=full_name,
            phone=None,
            password=None,
            is_verified=True
        )

    #log user to django
    auth_login(request,user)

    #send user to dashboard
    return redirect("/") 


@ensure_csrf_cookie
@login_required
def profile_page(request):

    #Current logged in user
    user = request.user

    return render(request, "users/profile.html",{"user" : user},)


@login_required
def edit_profile_page(request):

    user = request.user

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        profile_picture = request.FILES.get("profile_picture")

        name_error = None
        phone_error = None

        # Validate name
        if not full_name:
            name_error = "Full name is required."
        elif not validate_user_name(full_name):
            name_error = "Enter a valid full name."

        # Validate phone
        if phone and not validate_user_phone(phone):
            phone_error = "Phone number must contain exactly 10 digits."
        elif phone and User.objects.filter(phone=phone).exclude(pk=user.pk).exists():
            phone_error = "That phone number is already in use."

        if name_error or phone_error:
            return render(request, "users/edit_profile.html", {
                "user": user,
                "submitted_full_name": full_name,
                "submitted_phone": phone,
                "name_error": name_error,
                "phone_error": phone_error,
                "error": name_error or phone_error,
            })

        if profile_picture:
            user.profile_picture = profile_picture

        user.full_name = full_name
        user.phone = phone or None
        user.save()
        return redirect("/profile/")

    return render(request, "users/edit_profile.html", {"user": user})


def send_email_change_otp(email):

    otp = generate_otp() #generate new otp

    expires_at = get_otp_expiry() #new otp expiry time

    send_otp_email(email, otp, "email_change") # send otp to the new mail

    return otp, expires_at

@login_required
def request_email_change(request):

    if request.method != "POST": #only accept request through POST
        return JsonResponse({"error" : "POST request required"}, status=400)

    data = json.loads(request.body) #get new email from request
    new_email = data.get("email", "").strip().lower()

    if not new_email:
        return JsonResponse({"error": "Email is required"}, status=400)

    if User.objects.filter(email=new_email).exclude(pk=request.user.pk).exists():
        return JsonResponse({"error" : "Email is already in use"}, status=400)

    otp, expires_at = send_email_change_otp(new_email)#generate and send otp

    #Store the temporary email and otp in the users session
    request.session["email_change_data"]={
        "email" : new_email,
        "otp" :otp,
        "expires_at": expires_at.isoformat(),

    }

    return JsonResponse({"message" : "OTP send successfully"}, status=200)

@login_required
def verify_email_change(request):
    #Only POST accept
    if request.method != "POST":
        return JsonResponse({"error" : "POST request required"}, status=400)

    #Get user entered otp
    data = json.loads(request.body)
    otp = data.get("otp", "").strip()

    if not otp:
        return JsonResponse({"error" : "OTP is required"}, status=400)

    # Get the pending email-change data from the session
    email_change_data = request.session.get("email_change_data")

    if not email_change_data:
        return JsonResponse({"error" : "No email change request found"}, status=400)

    expires_at = datetime.fromisoformat(email_change_data["expires_at"])

    #check OTP expired or not
    if timezone.now()>expires_at:
        # Remove expired verification data
        request.session.pop("email_change_data", None)
        return JsonResponse({"error" : "OTP has expired"}, status=400)

    #check otp correct
    if str(otp) != str(email_change_data["otp"]):
        return JsonResponse({"error": "Invalid OTP "}, status=400)

    #Get current logged in user
    user = request.user
    # Update the user's email after successful verification
    user.email = email_change_data["email"]
    user.save(update_fields=["email", "updated_at"])

    #Remone temp. OTP data
    request.session.pop("email_change_data", None)

    return JsonResponse({"message" : "Email changed successfully"}, status=200)


@login_required
@require_POST
def add_address(request):
    # Read address data sent from the frontend
    data = json.loads(request.body)

    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    pin = data.get("pin", "").strip()
    address_line1 = data.get("address_line1", "").strip()
    city = data.get("city", "").strip()

    #Validation
    if not validate_user_name(full_name):
        return JsonResponse({"error": "Enter a valid full name"}, status=400)
    if not validate_user_phone(phone):
        return JsonResponse({"error": "Phone number must contain exactly 10 digits"}, status=400)
    if not validate_pin(pin):
        return JsonResponse({"error": "PIN code must contain exactly 6 digits"}, status=400)
    if not address_line1:
        return JsonResponse({"error": "Address Line 1 is required"}, status=400)
    if not validate_address_line(address_line1):
        return JsonResponse({"error": "Enter a valid Address Line 1"}, status=400)
    if not city:
        return JsonResponse({
        "error": "City is required"}, status=400)
    if not validate_city(city):
        return JsonResponse({
        "error": "Enter a valid city name"}, status=400)
    

    address = Address.objects.create(
        user=request.user,
        address_label=data.get("address_label", "").strip(),
        custom_label=(data.get("custom_label") or "").strip() or None,
        full_name=data.get("full_name", "").strip(),
        phone=data.get("phone", "").strip(),
        address_line1=data.get("address_line1", "").strip(),
        address_line2=(data.get("address_line2",) or "").strip() or None,
        city=data.get("city", "").strip(),
        state=data.get("state", "").strip(),
        country=data.get("country", "").strip(),
        pin=data.get("pin", "").strip(),
        is_default=data.get("is_default", False),
    )

    return JsonResponse({"message" : "Address added successfully", "address_id" : address.id,}, status=201)

@login_required
def address_page(request):
    #Show all addresses
    addresses = request.user.addresses.all()

    return render(request, "users/addresses.html",{"addresses":addresses,})

@login_required
@require_POST
def edit_address(request, address_id):

    # Get only the logged-in user's address
    try:
        address = Address.objects.get(
            id = address_id,
            user = request.user 
        )
    except Address.DoesNotExist:
        return JsonResponse({"error" : "Address not found"}, status=404)

    #Read the  updated address data
    data = json.loads(request.body)


    full_name = data.get("full_name", "").strip()
    phone = data.get("phone", "").strip()
    pin = data.get("pin", "").strip()
    address_line1 = data.get("address_line1", "").strip()
    city = data.get("city", "").strip()

    if not validate_user_name(full_name):
        return JsonResponse({"error": "Enter a valid full name"}, status=400)
    if not validate_user_phone(phone):
        return JsonResponse({"error": "Phone number must contain exactly 10 digits"}, status=400)
    if not validate_pin(pin):
        return JsonResponse({"error": "PIN code must contain exactly 6 digits"}, status=400)
    if not address_line1:
        return JsonResponse({"error": "Address Line 1 is required"}, status=400)
    if not validate_address_line(address_line1):
        return JsonResponse({"error": "Enter a valid Address Line 1"}, status=400)
    if not city:
        return JsonResponse({"error": "City is required"}, status=400)
    if not validate_city(city):
        return JsonResponse({"error": "Enter a valid city name"}, status=400)
    

    address.address_label = data.get("address_label", "").strip()
    address.custom_label = (data.get("custom_label") or "").strip() or None
    address.full_name = data.get("full_name", "").strip()
    address.phone = data.get("phone", "").strip()
    address.address_line1 = data.get("address_line1", "").strip()
    address.address_line2=(data.get("address_line2") or "").strip() or None
    address.city = data.get("city", "").strip()
    address.state = data.get("state", "").strip()
    address.country = data.get("country", "").strip()
    address.pin = data.get("pin", "").strip()
    address.is_default = data.get("is_default", False)

    #Save the updated address
    address.save()

    return JsonResponse({
        "message" :"Address updated successfully",
        "address_id": address.id, 
    }, status=200)

@login_required
@require_POST
def delete_address(request, address_id):
    # Get only the logged-in user's address

    try:
        address = Address.objects.get(
            id=address_id,
            user = request.user
        )
    except Address.DoesNotExist:
        return JsonResponse({"error" : "Address not found" }, status=404)

    address.delete()

    return JsonResponse({"message" : "Address deleted successfully"}, status=200)  

@login_required
@require_POST
def set_default_address(request, address_id):
    # Get only the logged-in user's address
    try:
        address = Address.objects.get(
            id=address_id,
            user=request.user
        )
    except Address.DoesNotExist:
        return JsonResponse({
            "error": "Address not found"
        }, status=404)

    # Remove default status from all of this user's addresses
    Address.objects.filter(
        user=request.user
    ).update(is_default=False)

    # Make the selected address the default
    address.is_default = True
    address.save(update_fields=["is_default"])

    return JsonResponse({
        "message": "Default address updated successfully",
        "address_id": address.id,}, status=200)



