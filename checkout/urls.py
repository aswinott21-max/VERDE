from django.urls import path
from . import  views

app_name = "checkout"

urlpatterns = [

    path("", views.checkout_page, name="checkout"),
    path('place-order/',views.place_order,name="place_order"),

    path("create-razorpay-payment/", views.create_razorpay_payment,name= "create_razorpay_payment"),
    path("verify-razorpay-payment/", views.verify_razorpay_payment_view, name="verify_razorpay_payment"),

    path("payment-success/", views.payment_success_view, name="payment_success"),
    path("payment-failure/", views.payment_failure_view, name="payment_failure"),
]