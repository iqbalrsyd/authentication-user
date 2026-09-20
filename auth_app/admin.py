from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import OneTimePassword, SocialIdentity, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_verified", "is_staff")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Verification", {"fields": ("is_verified",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )


@admin.register(OneTimePassword)
class OneTimePasswordAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "created_at", "expires_at", "attempt_count", "used_at")
    readonly_fields = ("otp_hash", "created_at")


@admin.register(SocialIdentity)
class SocialIdentityAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "email_at_link", "created_at")
    search_fields = ("user__email", "subject", "email_at_link")
    readonly_fields = ("created_at",)
