from django.urls import path

from orders.views.user_views import checkout_api


app_name = "orders"


urlpatterns = [
    path("checkout/", checkout_api, name="checkout"),
]