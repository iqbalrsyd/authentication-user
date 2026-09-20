from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import OneTimePassword, SocialIdentity, User
from .utils import generate_otp


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RegistrationAPITests(APITestCase):
    url = reverse("auth:register")
    payload = {
        "email": "person@example.com",
        "first_name": "Test",
        "last_name": "Person",
        "password": "A-strong-password-2026",
        "password2": "A-strong-password-2026",
    }

    def test_registration_creates_user_and_sends_hashed_otp(self):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("password", response.data)
        self.assertNotIn("code", response.data)

        user = User.objects.get(email=self.payload["email"])
        self.assertTrue(user.check_password(self.payload["password"]))
        self.assertFalse(user.is_verified)

        challenge = OneTimePassword.objects.get(user=user)
        self.assertNotIn(challenge.otp_hash, mail.outbox[0].body)
        raw_code = mail.outbox[0].body.split("code is ", 1)[1][:6]
        self.assertTrue(challenge.check_code(raw_code))
        self.assertEqual(mail.outbox[0].to, [user.email])

    def test_password_mismatch_does_not_create_user(self):
        payload = {**self.payload, "password2": "Something-else-2026"}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_registration_uses_same_response_without_sending_again(self):
        first_response = self.client.post(self.url, self.payload, format="json")
        second_response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.data, first_response.data)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    @patch("auth_app.utils.send_mail", return_value=0)
    def test_delivery_failure_rolls_back_registration(self, _send_mail):
        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(User.objects.exists())
        self.assertFalse(OneTimePassword.objects.exists())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailVerificationAPITests(APITestCase):
    register_url = reverse("auth:register")
    verify_url = reverse("auth:verify-email")
    registration = {
        "email": "person@example.com",
        "first_name": "Test",
        "last_name": "Person",
        "password": "A-strong-password-2026",
        "password2": "A-strong-password-2026",
    }

    def setUp(self):
        self.client.post(self.register_url, self.registration, format="json")
        self.user = User.objects.get(email=self.registration["email"])
        self.challenge = OneTimePassword.objects.get(user=self.user)
        self.code = mail.outbox[0].body.split("code is ", 1)[1][:6]

    def wrong_code(self):
        return "000000" if self.code != "000000" else "111111"

    def test_valid_code_verifies_user_and_consumes_challenge(self):
        response = self.client.post(
            self.verify_url,
            {"email": self.user.email, "code": self.code},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.challenge.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        self.assertIsNotNone(self.challenge.used_at)

    def test_wrong_code_increments_attempt_count(self):
        response = self.client.post(
            self.verify_url,
            {"email": self.user.email, "code": self.wrong_code()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.challenge.refresh_from_db()
        self.assertEqual(self.challenge.attempt_count, 1)
        self.assertFalse(self.user.is_verified)

    def test_expired_code_is_rejected(self):
        self.challenge.expires_at = timezone.now() - timedelta(seconds=1)
        self.challenge.save(update_fields=["expires_at"])

        response = self.client.post(
            self.verify_url,
            {"email": self.user.email, "code": self.code},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)

    def test_used_code_cannot_be_replayed(self):
        payload = {"email": self.user.email, "code": self.code}
        self.assertEqual(self.client.post(self.verify_url, payload, format="json").status_code, 200)
        self.assertEqual(self.client.post(self.verify_url, payload, format="json").status_code, 400)

    def test_attempt_limit_blocks_correct_code(self):
        self.challenge.max_attempts = 1
        self.challenge.save(update_fields=["max_attempts"])
        self.client.post(
            self.verify_url,
            {"email": self.user.email, "code": self.wrong_code()},
            format="json",
        )

        response = self.client.post(
            self.verify_url,
            {"email": self.user.email, "code": self.code},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserAndOTPUnitTests(TestCase):
    def test_create_superuser_sets_required_flags(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            first_name="Admin",
            last_name="User",
            password="admin-password",
        )
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_verified)

    def test_generate_otp_is_six_digits(self):
        code = generate_otp()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailOTPLoginAPITests(APITestCase):
    request_url = reverse("auth:login-otp-request")
    verify_url = reverse("auth:login-otp-verify")

    def setUp(self):
        self.recaptcha_patcher = patch("auth_app.views.verify_recaptcha", return_value=True)
        self.recaptcha = self.recaptcha_patcher.start()
        self.addCleanup(self.recaptcha_patcher.stop)
        self.user = User.objects.create_user(
            email="verified@example.com",
            first_name="Verified",
            last_name="User",
            password="A-strong-password-2026",
            is_verified=True,
        )

    def request_code(self):
        response = self.client.post(
            self.request_url,
            {"email": self.user.email, "recaptcha_token": "valid-test-token"},
            format="json",
        )
        code = mail.outbox[-1].body.split("login code is ", 1)[1][:6]
        return response, code

    def test_verified_user_can_exchange_login_otp_for_jwt(self):
        request_response, code = self.request_code()
        self.assertEqual(request_response.status_code, status.HTTP_202_ACCEPTED)

        response = self.client.post(
            self.verify_url,
            {"email": self.user.email, "code": code},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["email"], self.user.email)

        me_response = self.client.get(
            reverse("auth:me"),
            HTTP_AUTHORIZATION=f"Bearer {response.data['access']}",
        )
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["id"], self.user.id)

    def test_login_otp_is_single_use(self):
        _, code = self.request_code()
        payload = {"email": self.user.email, "code": code}
        self.assertEqual(self.client.post(self.verify_url, payload, format="json").status_code, 200)
        self.assertEqual(self.client.post(self.verify_url, payload, format="json").status_code, 400)

    def test_unverified_user_receives_generic_response_without_email(self):
        self.user.is_verified = False
        self.user.save(update_fields=["is_verified"])

        response = self.client.post(
            self.request_url,
            {"email": self.user.email, "recaptcha_token": "valid-test-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_recaptcha_blocks_login_email(self):
        self.recaptcha.return_value = False

        response = self.client.post(
            self.request_url,
            {"email": self.user.email, "recaptcha_token": "invalid-test-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(OneTimePassword.objects.exists())


class GoogleLoginAPITests(APITestCase):
    url = reverse("auth:login-google")
    claims = {
        "sub": "google-subject-123",
        "email": "google-user@gmail.com",
        "email_verified": True,
        "given_name": "Google",
        "family_name": "User",
    }

    @patch("auth_app.views.verify_google_credential")
    def test_google_login_creates_identity_and_returns_jwt(self, verify_credential):
        verify_credential.return_value = self.claims

        response = self.client.post(self.url, {"credential": "google-id-token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        user = User.objects.get(email=self.claims["email"])
        self.assertTrue(user.is_verified)
        self.assertFalse(user.has_usable_password())
        identity = SocialIdentity.objects.get(user=user)
        self.assertEqual(identity.subject, self.claims["sub"])

    @patch("auth_app.views.verify_google_credential")
    def test_repeated_google_login_does_not_duplicate_user(self, verify_credential):
        verify_credential.return_value = self.claims

        self.client.post(self.url, {"credential": "first-token"}, format="json")
        response = self.client.post(self.url, {"credential": "second-token"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(SocialIdentity.objects.count(), 1)
