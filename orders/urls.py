from django.urls import path

from orders.views.user_views import (order_list,order_detail,cancel_order_api,return_order_api,return_order_item_api,cancel_order_item_api,download_invoice)
from orders.views.admin_views import(admin_order_list,admin_order_details,admin_update_order_status,admin_update_return_status,admin_update_return_note)


app_name = "orders"


urlpatterns = [
    #Admin
    path("admin/", admin_order_list, name="admin_order_list"),
    path("admin/<str:order_number>/",admin_order_details, name="admin_order_details"),
    path("admin/<str:order_number>/status/",admin_update_order_status, name="admin_update_order_status"),
    path("admin/return/<int:return_id>/status/",admin_update_return_status,name="admin_update_return_status"),
    path("admin/return/<int:return_id>/note/", admin_update_return_note, name="admin_update_return_note"),
    #User
    path("",order_list,name="order_list"),
    path("<str:order_number>/", order_detail, name="order_detail"),
    path("<str:order_number>/cancel/", cancel_order_api,name="cancel_order"),
    path("<str:order_number>/return/", return_order_api, name="return_order"),
    path("<str:order_number>/item/<int:order_item_id>/return/",return_order_item_api,name="return_order_item"),
    path("<str:order_number>/item/<int:order_item_id>/cancel/", cancel_order_item_api,name="cancel_order_item"),
    path("<str:order_number>/invoice/", download_invoice, name="download_invoice"),

    

    
]