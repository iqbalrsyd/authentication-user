from django.db import models
from django.contrib.auth.models import AbstractUser, PermissionsMixin
from django.utils.translation import gettext_lazy as _
from .managers import UserManager
# Create your models here.

class User(AbstractUser, PermissionsMixin):
    email = models.EmailField(max_length=255, unique=True, verbose_name=_("Email Address"))
    first_name = models.CharField(max_length=255, verbose_name=_("First Name"))
    last_name = models.CharField(max_length=255, verbose_name=_("Last Name"))
    is_staff = models.BooleanField(default=False, verbose_name=_("Staff Status"))
    is_superuser = models.BooleanField(default=False, verbose_name=_("Superuser Status"))
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    is_verified = models.BooleanField(default=False, verbose_name=_("Verified"))
    date_joined = models.DateTimeField(auto_now_add=True, verbose_name=_("Date Joined"))
    last_login = models.DateTimeField(auto_now=True, verbose_name=_("Last Login"))
    
    USERNAME_FIELD = 'email'
    
    REQUIRED_FIELDS= ["first_name", "last_name"]
    
    objects = UserManager()
    
    def __str__(self) -> str:
        return self.email
    
    @property
    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    def tokens(self):
        pass
    
class OneTimePassword(models.model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    
    def __str__(self):
        return f"{self.user.first_name} - passcode"
    
    