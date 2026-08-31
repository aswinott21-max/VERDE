from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class User(AbstractUser):
    username = None

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    profile_picture = models.ImageField(upload_to="profile_pictures/", blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email" #To take email as username
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email