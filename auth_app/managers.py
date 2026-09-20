from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, first_name, last_name, password=None, **extra_fields):
        if not email:
            raise ValueError(_("The email address is required"))
        if not first_name:
            raise ValueError(_("The first name is required"))
        if not last_name:
            raise ValueError(_("The last name is required"))

        email = self.normalize_email(email)
        try:
            validate_email(email)
        except ValidationError as exc:
            raise ValueError(_("Enter a valid email address")) from exc

        user = self.model(email=email, first_name=first_name, last_name=last_name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True"))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True"))

        return self.create_user(email, first_name, last_name, password, **extra_fields)
