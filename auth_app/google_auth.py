from django.conf import settings
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token


class GoogleLoginError(Exception):
    pass


class GoogleLoginConfigurationError(GoogleLoginError):
    pass


def verify_google_credential(credential):
    if not settings.GOOGLE_OAUTH_CLIENT_ID:
        raise GoogleLoginConfigurationError("Google login is not configured.")

    try:
        claims = id_token.verify_oauth2_token(
            credential,
            Request(),
            settings.GOOGLE_OAUTH_CLIENT_ID,
        )
    except (GoogleAuthError, ValueError) as exc:
        raise GoogleLoginError("Invalid Google credential.") from exc

    if not claims.get("sub") or not claims.get("email") or claims.get("email_verified") is not True:
        raise GoogleLoginError("The Google account email is not verified.")

    return claims
