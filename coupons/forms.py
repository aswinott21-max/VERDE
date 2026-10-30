import logging
from django import forms
from coupons.models import Coupon
from django.utils import timezone
from datetime import UTC
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

class CouponForm(forms.ModelForm):
    IST = ZoneInfo("Asia/Kolkata")
    class Meta:
        model = Coupon
        fields = [
            "code",
            "coupon_name",
            "discount_type",
            "discount_value",
            "minimum_order_amount",
            "max_discount_amount",
            "start_date",
            "expiry_date",
            "usage_limit",
            "status",
        ]
    
    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get("start_date")
        expiry_date = cleaned_data.get("expiry_date")

        if start_date:
            start_date = timezone.make_naive(start_date, timezone.UTC)
            start_date = timezone.make_aware(start_date, self.IST)
            cleaned_data["start_date"] = start_date

        if expiry_date:
            expiry_date = timezone.make_naive(expiry_date, timezone.UTC)
            expiry_date = timezone.make_aware(expiry_date,self.IST)
            cleaned_data["expiry_date"]=expiry_date

        now = timezone.now().astimezone(self.IST)

        #apply past-date validation only when creating a new coupon.
        if not self.instance.pk:
            if start_date and start_date < now:
                self.add_error("start_date","Start date cannot be in the past.",)

            if expiry_date and expiry_date < now:
                self.add_error("expiry_date","Expiry date cannot be in the past.",)

        #this rule applies to both new and existing coupons.
        if start_date and expiry_date and expiry_date <= start_date:
            self.add_error("expiry_date", "Expiry date must be after the start date.",)

        #Minimum order amount must be greater than the fixed discount value
        discount_type = cleaned_data.get("discount_type")
        discount_value = cleaned_data.get("discount_value")
        minimum_order_amount = cleaned_data.get("minimum_order_amount")

        if (
            discount_type == "fixed"
            and discount_value is not None
            and minimum_order_amount is not None
            and minimum_order_amount <= discount_value):

            self.add_error("minimum_order_amount","Minimum order amount must be greater than the fixed discount value.")
        
        logger.info("Coupon date validation completed")

        return cleaned_data