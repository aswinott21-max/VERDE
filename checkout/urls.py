from django.urls import path
from . import  views

app_name = "checkout"

urlpatterns = [

    path("", views.checkout_page, name="checkout"),
    path('place-order/',views.place_order,name="place_order"),
    
]