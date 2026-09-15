import re
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

def validate_user_email(email):
    #Check emails valid format

    try:
        validate_email(email)
        return True
    except ValidationError:
        return False

def validate_user_phone(phone):
    # Phone number must contain exactly 10 digits
    return phone.isdigit() and len(phone) == 10

def validate_pin(pin):
    return pin.isdigit() and len(pin) ==6


def validate_user_name(name):
    return bool(re.fullmatch (r"[A-Za-z]+(?:[ '-][A-Za-z]+)*", name))


def validate_address_line(address):
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9\s,./'-]*", address))


def validate_city(city):
    return bool(re.fullmatch(r"[A-Za-z]+(?: [A-Za-z]+)*", city))



def validate_user_password(password):
    # Password must contain uppercase, lowercase, number,
    # special character, and at least 8 characters
    return bool(re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$",password))

def is_email_taken(email, User):#Check a mail alreaady registered
    return User.objects.filter(email=email).exists()

def is_phone_taken(phone, User):
    return User.objects.filter(phone=phone).exists()

