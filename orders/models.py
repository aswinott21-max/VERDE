from django.db import models

from users.models import User
from products.models import Product, ProductVariant


class Order(models.Model):

    user = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="orders",)
    address = models.ForeignKey("OrderAddress",on_delete=models.SET_NULL,null=True,blank=True,related_name="address_orders",)
    coupon_id = models.BigIntegerField(null=True, blank=True)
    order_number = models.CharField(max_length=100, unique=True)
    delivery_method = models.CharField(max_length=100)
    payment_method = models.CharField(max_length=100)
    discount_amount = models.DecimalField(max_digits=10,decimal_places=2,default=0,)
    shipping_amount = models.DecimalField(max_digits=10,decimal_places=2,default=0,)
    subtotal = models.DecimalField(max_digits=10,decimal_places=2,default=0,)
    total_amount = models.DecimalField(max_digits=10,decimal_places=2,default=0,)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name="items",)
    product = models.ForeignKey(Product,on_delete=models.PROTECT,related_name="order_items",)
    product_variant = models.ForeignKey(ProductVariant,on_delete=models.SET_NULL,null=True,blank=True,related_name="order_items",)
    product_name = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10,decimal_places=2,)
    total_price = models.DecimalField(max_digits=10,decimal_places=2,)
    discount_amount = models.DecimalField(max_digits=10,decimal_places=2,default=0,)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_item"

    def __str__(self):
        return f"OrderItem #{self.id} - Order #{self.order_id}"


class OrderAddress(models.Model):

    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name="address_snapshots",)
    address_label = models.CharField(max_length=50)
    custom_label = models.CharField(max_length=100, blank=True, null=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255,blank=True,null=True,)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pin = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_address"

    def __str__(self):
        return f"{self.full_name} - {self.city}"



class OrderStatusHistory(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name="status_history",)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "order_status_history"

    def __str__(self):
        return f"Order #{self.order_id} - {self.status}"