# Authenticator User

Authenticator User is a Django-based backend project for managing user registration and email verification. It uses a custom user model in which an email address replaces the traditional username as the primary login identifier.

## Purpose

The project is intended to provide the foundation for an authentication API. Its current focus is registering users, securely storing their passwords, generating one-time passwords (OTPs), and sending verification codes by email.

## Main Features

- Email-based user accounts with unique email addresses
- Custom user and superuser creation through a Django user manager
- First name, last name, active, staff, superuser, and verification status fields
- Password confirmation and a minimum password length during registration
- Six-digit OTP generation for email verification
- Storage of OTPs associated with individual users
- Django admin integration for user management
- Versioned registration route at `api/v1/auth/register/`

## Registration Flow

1. A client submits an email address, first name, last name, password, and password confirmation.
2. Django REST Framework validates the submitted data and checks that both passwords match.
3. The custom user manager normalizes and validates the email address, hashes the password, and saves the new user.
4. A six-digit OTP is generated and stored for that user.
5. The application attempts to send the OTP to the user's email address.

## Project Structure

- `authenticator_user/` contains the main Django configuration, including settings and root URL routing.
- `auth_app/models.py` defines the custom `User` and `OneTimePassword` models.
- `auth_app/managers.py` provides custom user and superuser creation logic.
- `auth_app/serializers.py` validates registration requests and creates users.
- `auth_app/views.py` handles the registration API request.
- `auth_app/utils.py` generates and sends email verification codes.
- `auth_app/urls.py` defines authentication-related routes.
- `auth_app/admin.py` exposes the custom user model in Django's admin interface.

## Technology

- Python
- Django 5.1
- Django REST Framework
- django-environ for environment-based configuration
- SQLite for local data storage
- Django's email framework for OTP delivery

## Current Status

This repository is an early-stage prototype rather than a production-ready authentication service. The registration and OTP concepts are present, but the project still requires configuration corrections and completion of the verification flow before it can run end to end. Automated tests, login and logout endpoints, token handling, OTP validation and expiration, resend controls, rate limiting, and production deployment settings are not yet implemented.

Sensitive configuration such as `SECRET_KEY`, `DEBUG`, and email settings should be supplied through environment variables and must not be committed to source control.
