import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail

def generate_otp():
    return random.randint(100000, 999999)

def get_otp_expiry():
    return timezone.now() + timedelta(seconds=60)

def send_otp_email(email, otp, purpose):

    if purpose == "signup":
        subject = "VERDÉ Email Verification OTP"
        message = ( "Hello,\n\n" "Thank you for signing up with VERDÉ.\n\n" f"Your email verification OTP is: {otp}\n\n" "This OTP is valid for 1 minute.\n" "Please do not share this OTP with anyone.\n\n" "If you did not request this OTP, you can safely ignore this email.\n\n" "Regards,\n" "VERDÉ Team" )

    elif purpose == "resend":
        subject = "VERDÉ Email Verification OTP"
        message = message = ( "Hello,\n\n" "Here is your new VERDÉ email verification OTP.\n\n" f"Your OTP is: {otp}\n\n" "This OTP is valid for 1 minute.\n" "Please do not share this OTP with anyone.\n\n" "Regards,\n" "VERDÉ Team" )

    elif purpose == "password_reset":
        subject = "VERDÉ Password Reset OTP"
        message =( "Hello,\n\n" "We received a request to reset your VERDÉ account password.\n\n" f"Your password reset OTP is: {otp}\n\n" "This OTP is valid for 1 minute.\n" "Please do not share this OTP with anyone.\n\n" "If you did not request a password reset, you can safely ignore this email.\n\n" "Regards,\n" "VERDÉ Team" )

    elif purpose == "email_change":
        subject = "VERDÉ Email Change Verification OTP"
        message = ( "Hello,\n\n" "We received a request to change the email address associated with your VERDÉ account.\n\n" f"Your verification OTP is: {otp}\n\n" "This OTP is valid for 1 minute.\n" "Please do not share this OTP with anyone.\n\n" "If you did not request this change, please secure your account.\n\n" "Regards,\n" "VERDÉ Team" )

    elif purpose == "password_change":
        subject = "VERDÉ Password Change OTP"
        message = ( "Hello,\n\n" "We received a request to change your VERDÉ account password.\n\n" f"Your password change OTP is: {otp}\n\n" "This OTP is valid for 1 minute.\n" "Please do not share this OTP with anyone.\n\n" "If you did not request this change, please secure your account.\n\n" "Regards,\n" "VERDÉ Team" )
    else:
        raise ValueError("Invalid OTP purpose")

    send_mail(subject,message,None, [email])