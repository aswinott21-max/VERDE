from django.urls import path
from .views.auth_views import (admin_login_page, admin_login, admin_forgot_password,admin_resend_otp,verify_admin_reset_password_otp,admin_reset_password,admin_logout,)
from .views.user_views import (toggle_user_status,admin_users_page,)
from .views.dashboard_views import admin_dashboard_page

urlpatterns=[

    path("admin-login/", admin_login_page, name="admin_login_page"),
    path("admin-login/process/", admin_login, name="admin_login"),
    path("admin-forgot-password/",admin_forgot_password,name="admin_forgot_password"),
    path("admin-verify-reset-password-otp/",verify_admin_reset_password_otp, name="verify_admin_reset_password_otp"),
    path("admin-reset-password/", admin_reset_password, name="admin_reset_password"),
    path("admin-resend-otp/",admin_resend_otp,name="admin_resend_otp"),
    path("admin-dashboard/",admin_dashboard_page,name="admin_dashboard_page",),
    path("admin-logout/", admin_logout, name="admin_logout"),
    path("admin-panel/users/<int:user_id>/toggle-status/",toggle_user_status,name="toggle_user_status"),
    path("admin-panel/users/",admin_users_page,name="admin_users_page"),



]
