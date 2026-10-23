import secrets
import string

from .models import ReferralCode

def generate_referral_code(user):
    #Return the customer's existing code or create a unique one
    existing_code = ReferralCode.objects.filter(user=user).first()
    if existing_code:
        return existing_code
    alphabet = string.ascii_uppercase + string.digits

    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(8))

        if not ReferralCode.objects.filter(code=code).exists():
            return ReferralCode.objects.create(user=user,code=code)
        