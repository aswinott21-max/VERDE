import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail

def generate_otp():
    return random.randint(100000, 999999)

def get_otp_expiry():
    return timezone.now() + timedelta(minutes=5)

def send_otp_email(email, otp, purpose):

    if purpose == "signup":
        subject = "VERDÉ Email Verification OTP"
        message = ( f"Your VERDÉ signup OTP is: {otp}\n\n" "This OTP is valid for 5 minutes.")

    elif purpose == "resend":
        subject = "VERDÉ Email Verification OTP"
        message = ( f"Your new VERDÉ signup OTP is: {otp}\n\n" "This OTP is valid for 5 minutes.")

    elif purpose == "password_reset":
        subject = "VERDÉ Password Reset OTP"
        message =( f"Your VERDÉ password reset OTP is: {otp}\n\n" "This OTP is valid for 5 minutes.")

    else:
        raise ValueError("Invalid OTP purpose")

    send_mail(subject,message,None, [email])