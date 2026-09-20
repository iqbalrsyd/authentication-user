from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import User


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(max_length=128, write_only=True)
    password2 = serializers.CharField(max_length=128, write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "password", "password2", "is_verified"]
        read_only_fields = ["id", "is_verified"]
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, value):
        normalized_email = User.objects.normalize_email(value)
        return normalized_email

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "The passwords do not match."})
        candidate = User(
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        validate_password(attrs["password"], user=candidate)
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        return User.objects.create_user(**validated_data)


class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    code = serializers.RegexField(regex=r"^\d{6}$", trim_whitespace=False)

    def validate_email(self, value):
        return User.objects.normalize_email(value)


class EmailLoginRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255)
    recaptcha_token = serializers.CharField(max_length=4096, trim_whitespace=False)

    def validate_email(self, value):
        return User.objects.normalize_email(value)


class EmailLoginVerifySerializer(VerifyEmailSerializer):
    pass


class GoogleLoginSerializer(serializers.Serializer):
    credential = serializers.CharField(max_length=8192, trim_whitespace=False)


class CurrentUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "is_verified"]
        read_only_fields = fields
