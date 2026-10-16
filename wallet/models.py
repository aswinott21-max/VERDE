from django.conf import settings
from django.db import models

# Create your models here.

class Wallet(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    balance = models.DecimalField(max_digits=12, decimal_places=2,default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wallet"

    def __str__(self):
        return f"Wallet #{self.pk}"

class WalletTransaction(models.Model):
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    reference_id = models.TextField(blank=True, default="")
    transaction_id = models.CharField(max_length=100, unique=True)
    transaction_type = models.CharField(max_length=20)
    wallet = models.ForeignKey(Wallet,on_delete=models.PROTECT, related_name="transactions")

    class Meta:
        db_table = "wallet_transactions"
        ordering = ["-created_at"]

    def __str__(self):
        return self.transaction_id

class WalletTopUp(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,related_name="wallet_topups")
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100,unique=True,null=True,blank=True)
    status = models.CharField(max_length=20, choices=[("PENDING", "Pending"),("COMPLETED", "Completed"),("FAILED", "Failed"),],default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "wallet_topups"
        ordering = ["-created_at"]

    def __str__(self):
        return f"wallet Top-Up #{self.pk}"
