from django.urls import path
from .admin_views import (add_category, category_dashboard,edit_category,toggle_category_status, set_category_offer)

urlpatterns = [
    path("admin/categories/",category_dashboard, name="category_dashboard"),
    path("admin/categories/add/", add_category,name="add_category"),
    path("admin/categories/<int:category_id>/edit/", edit_category, name="edit_category"),
    path("admin/categories/<int:category_id>/toggle-status/",toggle_category_status, name="toggle_category_status"),
    path("admin/categories/<int:category_id>/offer/", set_category_offer, name="set_category_offer"),
    


]