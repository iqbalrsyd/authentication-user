import requests
from django.conf import settings


class RecaptchaError(Exception):
    pass


class RecaptchaConfigurationError(RecaptchaError):
    pass


class RecaptchaServiceError(RecaptchaError):
    pass


def verify_recaptcha(token, remote_ip=None):
    if not settings.RECAPTCHA_SECRET_KEY:
        raise RecaptchaConfigurationError("reCAPTCHA is not configured.")

    if not token or len(token) > 4096:
        return False

    payload = {
        "secret": settings.RECAPTCHA_SECRET_KEY,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data=payload,
            timeout=settings.RECAPTCHA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        result = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RecaptchaServiceError("reCAPTCHA verification is unavailable.") from exc

    if result.get("success") is not True:
        return False

    allowed_hostnames = settings.RECAPTCHA_ALLOWED_HOSTNAMES
    if allowed_hostnames and result.get("hostname") not in allowed_hostnames:
        return False

    return True
