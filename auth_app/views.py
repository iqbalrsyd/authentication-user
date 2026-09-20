from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import Http404
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .google_auth import (
    GoogleLoginConfigurationError,
    GoogleLoginError,
    verify_google_credential,
)
from .models import OneTimePassword, SocialIdentity, User
from .recaptcha import (
    RecaptchaConfigurationError,
    RecaptchaServiceError,
    verify_recaptcha,
)
from .serializers import (
    CurrentUserSerializer,
    EmailLoginRequestSerializer,
    EmailLoginVerifySerializer,
    GoogleLoginSerializer,
    UserRegisterSerializer,
    VerifyEmailSerializer,
)
from .tokens import authentication_response
from .utils import EmailDeliveryError, send_code_to_user, send_login_code_to_user


class LoginDemoView(TemplateView):
    template_name = "auth_app/login_demo.html"

    def dispatch(self, request, *args, **kwargs):
        if not settings.AUTH_DEMO_ENABLED:
            raise Http404
        response = super().dispatch(request, *args, **kwargs)
        # Google Identity Services returns credentials to its opener via
        # postMessage. Django's default `same-origin` policy would detach the
        # cross-origin Google popup from this page.
        response["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["google_client_id"] = settings.GOOGLE_OAUTH_CLIENT_ID
        context["recaptcha_site_key"] = settings.RECAPTCHA_SITE_KEY
        return context


class RegisterUserView(GenericAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        response_body = {
            "message": "If registration can proceed, a verification code will be sent by email."
        }

        if User.objects.filter(email__iexact=serializer.validated_data["email"]).exists():
            return Response(response_body, status=status.HTTP_201_CREATED)

        try:
            with transaction.atomic():
                send_code_to_user(serializer.save())
        except IntegrityError:
            return Response(response_body, status=status.HTTP_201_CREATED)
        except EmailDeliveryError:
            return Response(
                {"message": "Account creation is temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(response_body, status=status.HTTP_201_CREATED)


class VerifyEmailView(GenericAPIView):
    serializer_class = VerifyEmailSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        invalid_response = Response(
            {"message": "The verification code is invalid or no longer available."},
            status=status.HTTP_400_BAD_REQUEST,
        )

        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(email__iexact=serializer.validated_data["email"])
                challenge = (
                    OneTimePassword.objects.select_for_update()
                    .filter(
                        user=user,
                        purpose=OneTimePassword.Purpose.EMAIL_VERIFICATION,
                        used_at__isnull=True,
                    )
                    .first()
                )
            except User.DoesNotExist:
                return invalid_response

            if challenge is None or not challenge.can_attempt:
                return invalid_response

            if not challenge.check_code(serializer.validated_data["code"]):
                challenge.attempt_count += 1
                challenge.save(update_fields=["attempt_count"])
                return invalid_response

            challenge.used_at = timezone.now()
            challenge.save(update_fields=["used_at"])
            user.is_verified = True
            user.save(update_fields=["is_verified"])

        return Response({"message": "Email verified successfully."}, status=status.HTTP_200_OK)


class EmailLoginRequestView(GenericAPIView):
    serializer_class = EmailLoginRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_body = {
            "message": "If the account can sign in, a login code will be sent by email."
        }

        try:
            captcha_valid = verify_recaptcha(
                token=serializer.validated_data["recaptcha_token"],
                remote_ip=request.META.get("REMOTE_ADDR"),
            )
        except (RecaptchaConfigurationError, RecaptchaServiceError):
            return Response(
                {"message": "Human verification is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not captcha_valid:
            return Response(
                {"recaptcha_token": ["Human verification failed. Please try again."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(
                email__iexact=serializer.validated_data["email"],
                is_active=True,
                is_verified=True,
            )
        except User.DoesNotExist:
            return Response(response_body, status=status.HTTP_202_ACCEPTED)

        try:
            with transaction.atomic():
                send_login_code_to_user(user)
        except EmailDeliveryError:
            return Response(
                {"message": "Login email is temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(response_body, status=status.HTTP_202_ACCEPTED)


class EmailLoginVerifyView(GenericAPIView):
    serializer_class = EmailLoginVerifySerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invalid_response = Response(
            {"message": "The login code is invalid or no longer available."},
            status=status.HTTP_400_BAD_REQUEST,
        )

        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(
                    email__iexact=serializer.validated_data["email"],
                    is_active=True,
                    is_verified=True,
                )
                challenge = (
                    OneTimePassword.objects.select_for_update()
                    .filter(
                        user=user,
                        purpose=OneTimePassword.Purpose.LOGIN,
                        used_at__isnull=True,
                    )
                    .first()
                )
            except User.DoesNotExist:
                return invalid_response

            if challenge is None or not challenge.can_attempt:
                return invalid_response

            if not challenge.check_code(serializer.validated_data["code"]):
                challenge.attempt_count += 1
                challenge.save(update_fields=["attempt_count"])
                return invalid_response

            now = timezone.now()
            challenge.used_at = now
            challenge.save(update_fields=["used_at"])
            user.last_login = now
            user.save(update_fields=["last_login"])
            response_body = authentication_response(user)

        return Response(response_body, status=status.HTTP_200_OK)


class GoogleLoginView(GenericAPIView):
    serializer_class = GoogleLoginSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            claims = verify_google_credential(serializer.validated_data["credential"])
        except GoogleLoginConfigurationError:
            return Response(
                {"message": "Google login is temporarily unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except GoogleLoginError:
            return Response(
                {"message": "The Google credential is invalid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = User.objects.normalize_email(claims["email"])
        subject = claims["sub"]

        with transaction.atomic():
            identity = (
                SocialIdentity.objects.select_related("user")
                .filter(provider=SocialIdentity.Provider.GOOGLE, subject=subject)
                .first()
            )

            if identity is not None:
                user = identity.user
            else:
                user = User.objects.filter(email__iexact=email).first()
                if user is None:
                    user = User.objects.create_user(
                        email=email,
                        first_name=claims.get("given_name") or "Google",
                        last_name=claims.get("family_name") or "User",
                        password=None,
                        is_verified=True,
                    )
                else:
                    existing_google_identity = SocialIdentity.objects.filter(
                        provider=SocialIdentity.Provider.GOOGLE,
                        user=user,
                    ).exists()
                    if existing_google_identity:
                        return Response(
                            {"message": "This account is linked to another Google identity."},
                            status=status.HTTP_409_CONFLICT,
                        )
                    if not user.is_verified:
                        user.is_verified = True
                        user.save(update_fields=["is_verified"])

                SocialIdentity.objects.create(
                    user=user,
                    provider=SocialIdentity.Provider.GOOGLE,
                    subject=subject,
                    email_at_link=email,
                )

            if not user.is_active:
                return Response(
                    {"message": "This account is unavailable."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            user.last_login = timezone.now()
            user.save(update_fields=["last_login"])
            response_body = authentication_response(user)

        return Response(response_body, status=status.HTTP_200_OK)


class CurrentUserView(GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data, status=status.HTTP_200_OK)
