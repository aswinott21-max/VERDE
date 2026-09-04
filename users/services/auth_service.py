from django.contrib.auth.hashers import make_password

def hash_user_password(password): # Convert the plain password into a secure Django hash

    return make_password(password)