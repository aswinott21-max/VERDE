from django.urls import path

from .views.admin_views import (admin_coupons_page,add_coupon,edit_coupon,toggle_coupon_status)
from .views.user_views import user_coupons_page

urlpatterns = [
    #Admin
    path("admin/coupons/", admin_coupons_page, name="admin_coupons_page"),
    path("admin/coupons/add/", add_coupon, name= "add_coupon"),
    path("admin/coupons/edit/<int:coupon_id>/",edit_coupon,name="edit_coupon"),
    path("admin/coupons/toggle-status/<int:coupon_id>/",toggle_coupon_status,name="toggle_coupon_status"),


    #User
    path("coupons/", user_coupons_page, name="user_coupons_page"),



    
]