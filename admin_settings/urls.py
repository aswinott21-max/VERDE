from django.urls import path
from .views import (admin_settings_page,update_admin_profile,request_admin_email_change,verify_admin_email_change,send_admin_password_change_otp,verify_admin_password_change_otp,change_admin_password)

app_name = "admin_settings"

urlpatterns =[
    path("",admin_settings_page,name="admin_settings"),
    path("profile/update/",update_admin_profile,name="update_admin_profile"),
    path("email/request-otp/", request_admin_email_change, name="request_admin_email_change"),
    path("email/verify-otp/", verify_admin_email_change, name="verify_admin_email_change"),
    path("password/send-otp/",send_admin_password_change_otp,name="send_admin_password_change_otp",),
    path("password/verify-otp/",verify_admin_password_change_otp,name="verify_admin_password_change_otp",),
    path("password/update/",change_admin_password,name="change_admin_password",),


]