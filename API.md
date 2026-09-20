# Authentication API

Base path: `/api/v1/auth/`

Requests and responses use JSON. Validation errors use HTTP `400` and follow the
Django REST Framework field-error format. Passwords and verification codes are
never returned by the API.

## Register

`POST /api/v1/auth/register/`

```json
{
  "email": "person@example.com",
  "first_name": "Test",
  "last_name": "Person",
  "password": "A-strong-password-2026",
  "password2": "A-strong-password-2026"
}
```

Success (`201`):

```json
{
  "message": "If registration can proceed, a verification code will be sent by email."
}
```

An already-registered email receives the same response and no additional email.
This prevents the endpoint from disclosing whether an account exists.

If email delivery fails, the user and challenge are rolled back and the endpoint
returns `503`, so the registration can be retried safely.

## Verify email

`POST /api/v1/auth/verify-email/`

```json
{
  "email": "person@example.com",
  "code": "012345"
}
```

Success (`200`):

```json
{"message": "Email verified successfully."}
```

An unknown account, expired code, reused code, incorrect code, or exhausted
attempt limit receives the same response (`400`):

```json
{"message": "The verification code is invalid or no longer available."}
```

Codes expire after `OTP_EXPIRY_SECONDS` (10 minutes by default), are single-use,
and allow `OTP_MAX_ATTEMPTS` failed submissions (5 by default).

## Create login CAPTCHA

`POST /api/v1/auth/captcha/login-otp/`

The response contains a public challenge ID, a base64 PNG image, and its lifetime:

```json
{
  "captcha_id": "2f8be7e9-2cef-4608-a674-640e6d5b90ab",
  "image": "data:image/png;base64,...",
  "expires_in": 120
}
```

The six-character answer is never returned or stored as plain text. CAPTCHA
challenges are case-insensitive, single-use, expire after two minutes by default,
and allow three failed attempts.

## Request email login OTP

`POST /api/v1/auth/login/otp/request/`

```json
{
  "email": "person@example.com",
  "captcha_id": "2f8be7e9-2cef-4608-a674-640e6d5b90ab",
  "captcha_answer": "A7K29P"
}
```

The backend consumes a valid CAPTCHA before looking up the account. A failed,
expired, exhausted, or reused CAPTCHA returns `400`. After a successful CAPTCHA,
the endpoint returns the same `202` response for unknown, inactive, unverified,
and eligible accounts so it does not disclose account state. Eligible accounts
receive a single-use login code by email.

## Verify email login OTP

`POST /api/v1/auth/login/otp/verify/`

```json
{"email": "person@example.com", "code": "012345"}
```

A valid code returns a 15-minute access token, a 7-day refresh token, and the
current user. Invalid, expired, exhausted, and reused codes all return the same
`400` response.

## Sign in with Google

`POST /api/v1/auth/login/google/`

```json
{"credential": "GOOGLE_ID_TOKEN_FROM_GOOGLE_IDENTITY_SERVICES"}
```

The frontend obtains `credential` from the official Google Identity Services
button. The backend verifies its signature, audience, issuer, expiry, and
verified email before linking the stable Google `sub` identifier. A successful
request returns the same access/refresh response as email OTP login.

Set `GOOGLE_OAUTH_CLIENT_ID` to the OAuth 2.0 Web Client ID used by the frontend.

## Refresh access token

`POST /api/v1/auth/token/refresh/`

```json
{"refresh": "REFRESH_TOKEN"}
```

## Current user

`GET /api/v1/auth/me/`

```text
Authorization: Bearer ACCESS_TOKEN
```

## Local setup

1. Create a virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and replace the development values.
3. Run `python manage.py migrate`.
4. Run `python manage.py test`.

Production must use an SMTP backend and must provide its secrets through the
environment. The default console backend is intended only for local development.
