from django.urls import path
from .admin_views import (product_dashboard,add_product,add_pot_product,add_equipment_product,add_product_by_category,get_product_edit_data_view,edit_product,toggle_product_status,upload_variant_images,upload_product_images,delete_product_image_view,set_product_offer,)
from .user_views import (product_list,product_detail)
urlpatterns = [
    # Admin
    path("admin/products/", product_dashboard, name="product_dashboard"),

    path("admin/products/add/<str:parent_category_name>/",add_product_by_category,name="add_product_by_category"),
    path("admin/products/<int:product_id>/edit/", edit_product, name="edit_product"),
    path("admin/products/<int:product_id>/toggle-status/", toggle_product_status, name="toggle_product_status"),
    path("admin/products/variants/<int:variant_id>/images/", upload_variant_images, name="upload_variant_images"),
    path("admin/products/<int:product_id>/images/",upload_product_images,name="upload_product_images"),
    path("admin/products/<int:product_id>/edit-data/", get_product_edit_data_view, name="get_product_edit_data"),
    path("admin/products/<int:product_id>/images/<int:image_id>/delete/", delete_product_image_view, name="delete_product_image_view"),
    path("admin/products/<int:product_id>/offer/",set_product_offer,name="set_product_offer"),


    # User
    path("products/", product_list, name="product_list"),
    path("products/<int:product_id>/",product_detail,name="product_detail",),

 


]