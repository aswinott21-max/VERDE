from django.db import models

from users.models import User
from orders.models import Order
# Create your models here.

class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES =(("percentage", "Percentage"),("fixed","Fixed Amount"),)
    STATUS_CHOICES = (("active", "Active"),("disabled","Disabled"),)
    code = models.CharField(max_length=50, unique=True)
    coupon_name = models.CharField(max_length=150)
    discount_type = models.CharField(max_length=20,choices=DISCOUNT_TYPE_CHOICES)
    discount_value = models.DecimalField(max_digits=10,decimal_places=2)
    minimum_order_amount = models.DecimalField(max_digits=10,decimal_places=2,default=0)
    max_discount_amount = models.DecimalField(max_digits=10,decimal_places=2,null=True,blank=True)
    start_date = models.DateTimeField()
    expiry_date = models.DateTimeField()
    usage_limit = models.PositiveBigIntegerField(null=True,blank=True)
    used_count = models.PositiveBigIntegerField(default=0)
    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "coupons"

    def __str__(self):
        return self.code


class CouponUsage(models.Model):
    coupon = models.ForeignKey(Coupon,on_delete=models.CASCADE,related_name="usages")
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="coupon_usage")
    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name="coupon_usage")
    discount_amount = models.DecimalField(max_digits=10,decimal_places=2)
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "coupon_usage"

    def __str__(self):
        return f"{self.user.email} - {self.coupon.code}"
    