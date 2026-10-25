from django.urls import path

from .views.admin_view import admin_referrals_page
from .views.user_views import user_referrals_page

app_name = "referrals"

urlpatterns =[
    #Admin
    path("admin/", admin_referrals_page, name="admin_referrals_page"),


    #User
    path("my-referrals/", user_referrals_page, name="user_referrals_page"),

]