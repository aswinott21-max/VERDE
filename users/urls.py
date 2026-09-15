from django.urls import path
from .views import (signup, verify_otp,create_account, resend_otp, signup_page, verify_otp_page,login_page,login, dashboard_page,logout, forgot_password_page,forgot_password,reset_password_otp_page,verify_reset_password_otp,reset_password_page,reset_password,home_page,google_login, google_callback, profile_page, edit_profile_page,request_email_change,verify_email_change,  send_change_password_otp,verify_change_password_otp,change_password,address_page,add_address,edit_address,delete_address,set_default_address)

urlpatterns = [
    path("signup/", signup, name="signup"),
    path("verify-otp/", verify_otp, name="verify_otp"),
    path("create-account/", create_account, name="create_account"),
    path("resend-otp/", resend_otp, name="resend_otp"),
    path("signup-page/", signup_page, name="signup_page"),
    path("verify-otp-page/", verify_otp_page, name="verify_otp_page"),
    path("login-page/", login_page, name="login_page"),
    path("login/", login,name="login"),
    path("dashboard/", dashboard_page, name="dashboard"),
    path("logout/", logout, name="logout"),
    path("forgot-password/", forgot_password_page, name="forgot_password_page"),
    path("forgot-password/send-otp/", forgot_password, name="forgot_password"),
    path("reset-password-otp/", reset_password_otp_page, name="reset_password_otp"),
    path("reset-password/verify-otp/", verify_reset_password_otp, name="verify_reset_password_otp"),
    path("reset-password/", reset_password_page, name="reset_password"),
    path("reset-password/change/",reset_password,name="reset_password"),
    path("", home_page, name="home"),

    path("google/login/", google_login, name="google_login"),
    path("google/callback/", google_callback, name="google_callback"),
    
    path("profile/", profile_page,name="profile"),
    path("profile/edit/", edit_profile_page, name="edit_profile"),
    path("profile/change-email/", request_email_change, name="request_email_change"),
    path("profile/verify-email/", verify_email_change, name="verify_email_change"),
    path("profile/change-password/send-otp/", send_change_password_otp, name="send_change_password_otp"),
    path("profile/change-password/verify-otp/", verify_change_password_otp, name="verify_change_password_otp"),
    path("profile/change-password/", change_password, name="change_password"),
    path("profile/addresses/add/", add_address, name="add_address"),
    path("profile/addresses/", address_page, name="address_page"),
    path("profile/addresses/<int:address_id>/edit/", edit_address, name="edit_address"),
    path("profile/addresses/<int:address_id>/delete/", delete_address, name="delete_address"),
    path("profile/addresses/<int:address_id>/set-default/",set_default_address,name="set_default_address"),



    
]