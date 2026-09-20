from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CurrentUserView,
    EmailLoginRequestView,
    EmailLoginVerifyView,
    GoogleLoginView,
    LoginCaptchaView,
    LoginDemoView,
    RegisterUserView,
    VerifyEmailView,
)


app_name = "auth"

urlpatterns = [
    path("demo/", LoginDemoView.as_view(), name="login-demo"),
    path("captcha/login-otp/", LoginCaptchaView.as_view(), name="login-captcha"),
    path("register/", RegisterUserView.as_view(), name="register"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("login/otp/request/", EmailLoginRequestView.as_view(), name="login-otp-request"),
    path("login/otp/verify/", EmailLoginVerifyView.as_view(), name="login-otp-verify"),
    path("login/google/", GoogleLoginView.as_view(), name="login-google"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", CurrentUserView.as_view(), name="me"),
]
