import secrets
import string
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import OneTimePassword


logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    pass


def generate_otp(length=6):
    return "".join(secrets.choice(string.digits) for _ in range(length))


def _send_otp(user, purpose, subject, message_template):
    raw_code = generate_otp()

    OneTimePassword.objects.filter(
        user=user,
        purpose=purpose,
        used_at__isnull=True,
    ).update(used_at=timezone.now())

    challenge = OneTimePassword(
        user=user,
        purpose=purpose,
        expires_at=OneTimePassword.expiry_from_now(),
        max_attempts=settings.OTP_MAX_ATTEMPTS,
    )
    challenge.set_code(raw_code)
    challenge.save()

    try:
        delivered = send_mail(
            subject=subject,
            message=message_template.format(
                first_name=user.first_name,
                code=raw_code,
                minutes=settings.OTP_EXPIRY_SECONDS // 60,
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as exc:
        logger.exception("OTP email delivery failed for user_id=%s purpose=%s", user.pk, purpose)
        raise EmailDeliveryError("The OTP email could not be delivered.") from exc
    if delivered != 1:
        raise EmailDeliveryError("The OTP email could not be delivered.")

    return challenge


def send_code_to_user(user):
    return _send_otp(
        user=user,
        purpose=OneTimePassword.Purpose.EMAIL_VERIFICATION,
        subject="Email verification code",
        message_template=(
            "Hello {first_name},\n\n"
            "Your verification code is {code}. "
            "It expires in {minutes} minutes.\n\n"
            "If you did not create this account, you can ignore this email."
        ),
    )


def send_login_code_to_user(user):
    return _send_otp(
        user=user,
        purpose=OneTimePassword.Purpose.LOGIN,
        subject="Your login code",
        message_template=(
            "Hello {first_name},\n\n"
            "Your login code is {code}. "
            "It expires in {minutes} minutes.\n\n"
            "If you did not request this login, you can ignore this email."
        ),
    )
