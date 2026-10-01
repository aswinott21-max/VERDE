from django.db import models
from users.models import User
from products.models import Product, ProductVariant
# Create your models here.

class Cart(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name= "carts", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "Cart"

    def __str__(self):
        return f"Cart #{self.id} - User: {self.user}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete= models.CASCADE,related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE,related_name="cart_items")
    product_variant = models.ForeignKey(ProductVariant, on_delete= models.CASCADE, null=True, blank=True, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2,default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cart_item"

    def __str__(self):
        return f"CartItem #{self.id} - Cart #{self.cart_id}"

    @property
    def total_price(self):
        return self.quantity * self.unit_price
    
