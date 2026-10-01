from django.urls import path

from cart.views.user_views import (cart_page,view_cart_api,add_to_cart_api,remove_from_cart_api,update_cart_quantity_api,)


app_name = "cart"
urlpatterns = [
    path("", view_cart_api, name="view_cart"),
    path("page/", cart_page, name="cart_page"),
    path("add/", add_to_cart_api, name="add_to_cart"),
    path("remove/", remove_from_cart_api, name="remove_from_cart"),
    path("update/", update_cart_quantity_api, name="update_cart_quantity"),
    
]