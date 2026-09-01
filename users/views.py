import json
from .models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

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

    #Check email and phone already exist
    if User.objects.filter (email=email).exists():
        return JsonResponse({
            "error" : "Email already exists"
        }, status=400)

    if User.objects.filter(phone=phone).exists():
        return JsonResponse({
            "error":"phone number already exists"
        }, status=400)

    #Check password confirmation
    if password != confirm_password:
        return JsonResponse({
            "error" : "Passwords do not match"
        }, status = 400)

    #Create user
    user = User.objects.create_user(
        email=email,
        full_name = name,
        password=password,
        phone = phone
    )



    return JsonResponse({
        "message" : "Data received successfully",
        "email" : user.email,
    },status=201)
