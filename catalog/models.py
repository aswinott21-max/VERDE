from django.db import models

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True,blank=True,related_name="subcategories")

    discount_value = models.DecimalField(max_digits=10, decimal_places=2,default=0)
    offer_start_at =models.DateTimeField(null=True, blank=True)
    offer_end_at=models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)