from django.urls import path
from .views import (signup, verify_otp,create_account, resend_otp, signup_page, verify_otp_page,login_page,login, dashboard_page,logout, forgot_password_page,forgot_password,reset_password_otp_page,verify_reset_password_otp,reset_password_page,reset_password)

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

]