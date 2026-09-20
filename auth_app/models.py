import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    username = None
    email = models.EmailField(max_length=255, unique=True, verbose_name=_("Email address"))
    first_name = models.CharField(max_length=255, verbose_name=_("First name"))
    last_name = models.CharField(max_length=255, verbose_name=_("Last name"))
    is_verified = models.BooleanField(default=False, verbose_name=_("Verified"))

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    def __str__(self):
        return self.email


class OneTimePassword(models.Model):
    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = "email_verification", _("Email verification")
        LOGIN = "login", _("Login")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="one_time_passwords",
    )
    otp_hash = models.CharField(max_length=128)
    purpose = models.CharField(
        max_length=32,
        choices=Purpose.choices,
        default=Purpose.EMAIL_VERIFICATION,
    )
    expires_at = models.DateTimeField()
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "purpose", "created_at"])]

    def __str__(self):
        return f"{self.user_id} - {self.purpose}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def can_attempt(self):
        return self.used_at is None and not self.is_expired and self.attempt_count < self.max_attempts

    def set_code(self, raw_code):
        self.otp_hash = make_password(raw_code)

    def check_code(self, raw_code):
        return check_password(raw_code, self.otp_hash)

    @classmethod
    def expiry_from_now(cls):
        return timezone.now() + timedelta(seconds=settings.OTP_EXPIRY_SECONDS)


class CaptchaChallenge(models.Model):
    class Purpose(models.TextChoices):
        LOGIN_OTP = "login_otp", _("Login OTP")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    answer_hash = models.CharField(max_length=64)
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["purpose", "created_at"])]

    @staticmethod
    def normalize_answer(raw_answer):
        return "".join(raw_answer.split()).upper()

    def set_answer(self, raw_answer):
        normalized = self.normalize_answer(raw_answer)
        self.answer_hash = salted_hmac(
            "auth_app.captcha",
            f"{self.pk}:{normalized}",
        ).hexdigest()

    def check_answer(self, raw_answer):
        normalized = self.normalize_answer(raw_answer)
        candidate = salted_hmac(
            "auth_app.captcha",
            f"{self.pk}:{normalized}",
        ).hexdigest()
        return constant_time_compare(candidate, self.answer_hash)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def can_attempt(self):
        return self.used_at is None and not self.is_expired and self.attempt_count < self.max_attempts

    @classmethod
    def expiry_from_now(cls):
        return timezone.now() + timedelta(seconds=settings.CAPTCHA_EXPIRY_SECONDS)

    def __str__(self):
        return f"{self.purpose} - {self.pk}"


class SocialIdentity(models.Model):
    class Provider(models.TextChoices):
        GOOGLE = "google", _("Google")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="social_identities",
    )
    provider = models.CharField(max_length=32, choices=Provider.choices)
    subject = models.CharField(max_length=255)
    email_at_link = models.EmailField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "subject"],
                name="unique_social_provider_subject",
            ),
            models.UniqueConstraint(
                fields=["provider", "user"],
                name="unique_social_provider_user",
            ),
        ]

    def __str__(self):
        return f"{self.provider} - {self.user_id}"
