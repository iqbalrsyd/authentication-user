from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import CurrentUserSerializer


def authentication_response(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "user": CurrentUserSerializer(user).data,
    }
