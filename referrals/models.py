from decimal import Decimal

from django.conf import settings
from django.db import models

from django.conf import settings
from django.db import models
from django.db.models import Q


class ReferralOffer(models.Model):

    reward_amount = models.DecimalField(max_digits=10,decimal_places=2,default=Decimal("100.00"),)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "referral_offer"
        constraints = [
            models.UniqueConstraint(
                fields=["is_active"],
                condition=Q(is_active=True),
                name="one_active_referral_offer",
            ),
        ]

    def __str__(self):
        return f"Referral reward: ₹{self.reward_amount}"


class ReferralCode(models.Model):
    #Stores the unique referral code owned by each customer
    user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="referral_code_record",)
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "referral_codes"

    def __str__(self):
        return self.code


class Referral(models.Model):
    #Records a customer's referral signup and qualification status

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ELIGIBLE = "ELIGIBLE", "Eligible"
        REWARDED = "REWARDED", "Rewarded"
        INELIGIBLE = "INELIGIBLE", "Ineligible"
        MANUAL_REVIEW = "MANUAL_REVIEW", "Manual review"

    referrer = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="referrals_made",)
    referred_user = models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="referral_received",)
    referral_code = models.CharField(max_length=50)
    referral_offer = models.ForeignKey(ReferralOffer,on_delete=models.PROTECT,related_name="referrals",)
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2)
    qualifying_order = models.ForeignKey("orders.Order",on_delete=models.PROTECT,null=True,blank=True,related_name="referral_records",)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING,)
    disqualification_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "referrals"
        constraints = [
            models.CheckConstraint(
                condition=~Q(referrer=models.F("referred_user")),
                name="referral_no_self_referral",
            ),
        ]

    def __str__(self):
        return f"Referral #{self.pk}: {self.referrer_id} → {self.referred_user_id}"


class ReferralReward(models.Model):
    #Tracks each recipient's reward independently for safe retries
    class RecipientRole(models.TextChoices):
        REFERRER = "REFERRER", "Referrer"
        REFERRED = "REFERRED", "Referred customer"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CREDITED = "CREDITED", "Credited"
        MANUAL_REVIEW = "MANUAL_REVIEW", "Manual review"

    referral = models.ForeignKey(Referral,on_delete=models.PROTECT,related_name="rewards",)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="referral_rewards",)
    recipient_role = models.CharField(max_length=10,choices=RecipientRole.choices,)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20,choices=Status.choices,default=Status.PENDING,)
    wallet_transaction = models.ForeignKey("wallet.WalletTransaction",on_delete=models.PROTECT,null=True,blank=True,related_name="referral_rewards",)
    credited_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "referral_rewards"
        constraints = [
            models.UniqueConstraint(
                fields=["referral", "recipient_role"],
                name="unique_referral_reward_per_role",
            ),
        ]

    def __str__(self):
        return f"{self.recipient_role} reward for referral #{self.referral_id}"


