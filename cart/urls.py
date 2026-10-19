from django.urls import path

from cart.views.user_views import (cart_page,view_cart_api,add_to_cart_api,remove_from_cart_api,update_cart_quantity_api,available_coupons_api,apply_coupon,remove_coupon)


app_name = "cart"
urlpatterns = [
    path("", view_cart_api, name="view_cart"),
    path("page/", cart_page, name="cart_page"),
    path("add/", add_to_cart_api, name="add_to_cart"),
    path("availabe_coupons_api",available_coupons_api,name="available_coupons"),
    path("apply-coupon/",apply_coupon, name="apply_coupon"),
    path("remove-coupon/",remove_coupon, name="remove_coupon"),
    path("remove/", remove_from_cart_api, name="remove_from_cart"),
    path("update/", update_cart_quantity_api, name="update_cart_quantity"),
    
]