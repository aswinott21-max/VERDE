import random
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
def otp_generator():
    return random.randint(100000,999999)

def otp_expiry_time():
    return timezone.now()+timedelta(seconds=60)

stored_otp = otp_generator()
entered_otp="489567"
expiry_time=otp_expiry_time()

def verify_otp(stored_otp,entered_otp,expiry_time):
    return stored_otp==entered_otp and expiry_time>timezone.now()

