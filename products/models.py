from django.db import models
from users.models import User
from catalog.models import Category
from django.core.validators import MinValueValidator, MaxValueValidator
# Create your models here.

class Product(models.Model):
    # Product belongs to a category
    category = models.ForeignKey(Category,on_delete=models.PROTECT, related_name="products")

    name = models.CharField(max_length=255)
    description = models.TextField()

    regular_price = models.DecimalField(max_digits=10, decimal_places=2)

    product_offer = models.DecimalField(max_digits=10,decimal_places=2,default=0)
    offer_start_at = models.DateTimeField(blank=True,null=True)
    offer_ends_at = models.DateTimeField(blank=True,null=True)

    stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now= True)


class ProductVariant(models.Model):

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")

    color = models.CharField(max_length=100)
    size = models.CharField(max_length=100)

    price = models.DecimalField(max_digits=10,decimal_places=2)

    stock_quantity = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ProductImage(models.Model):
    # Direct product image — used for Plants and Equipment
    product = models.ForeignKey(Product,on_delete=models.CASCADE,related_name="product_images", null=True, blank=True)

   
    # Variant image — used for Pots
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="images", null=True,blank=True)

    image_url = models.ImageField(upload_to="product_images/")
    is_primary = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
class Review(models.Model):
    id = models.BigAutoField(primary_key=True)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    order_item_id = models.BigIntegerField(null=True, blank=True)
    product = models.ForeignKey(Product,on_delete=models.CASCADE, related_name="reviews",db_column="produc_id")
    product_variant = models.ForeignKey(ProductVariant,on_delete=models.SET_NULL, null=True, blank=True, related_name="reviews", db_column="product_variant_id")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="product_reviews", db_column="user_id")
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    review_text = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "reviews"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Review #{self.id} - {self.product.name} ({self.rating}★)"

class ReviewImage(models.Model):
    id  = models.BigAutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)
    image_url = models.CharField(max_length=500)
    review = models.ForeignKey(Review, on_delete=models.CASCADE,related_name="images",db_column="review_id")

    class Meta:
        db_table = "review_image"

    def __str__(self):
        return f"image #{self.id} for Review #{self.review_id}"
    
 