from django.db import models

from users.models import User
from products.models import Product, ProductVariant


class Wishlist(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="wishlists",)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wishlist"

    def __str__(self):
        return f"Wishlist - {self.user.email}"


class WishlistItem(models.Model):
    wishlist = models.ForeignKey(Wishlist,on_delete=models.CASCADE,related_name="items",)
    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name="wishlist_items",)
    product_variant = models.ForeignKey(ProductVariant,on_delete=models.CASCADE,null=True,blank=True,related_name="wishlist_items",)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "wishlist_items"

    def __str__(self):
        return f"{self.product.name} - {self.wishlist.user.email}"