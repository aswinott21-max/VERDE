from django.urls import path
from wishlist.views import (add_to_wishlist_api,remove_from_wishlist_api,wishlist_page)

app_name = "wishlist"

urlpatterns = [
    path("",wishlist_page,name="wishlist_page"),
    path("add/",add_to_wishlist_api, name="add_to_wishlist"),
    path("remove/",remove_from_wishlist_api,name="remove_from_wishlist"),
]