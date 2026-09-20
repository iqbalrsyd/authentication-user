# Authenticator User Expansion Plan

## 1. Product Vision

Expand the current Django project into a secure, reusable authentication service that supports multiple ways to register, sign in, verify identity, recover accounts, and prevent automated abuse.

The service should provide:

- Several authentication methods under one user account
- Email, phone, social, passkey, and multi-factor verification options
- A provider-independent CAPTCHA system
- Configurable security policies for different endpoints and risk levels
- Auditing, monitoring, testing, and production-ready deployment

## 2. Guiding Principles

- Keep authentication methods modular so they can be enabled or disabled independently.
- Separate identity verification, authentication, authorization, and bot protection.
- Never treat CAPTCHA as proof of a user's identity; CAPTCHA only helps detect automated abuse.
- Store secrets outside source control and encrypt sensitive data where appropriate.
- Prefer short-lived, single-use verification challenges.
- Apply rate limits and abuse controls at the account, IP, device, and endpoint levels.
- Return consistent API responses without revealing whether an account exists.

## 3. Phase 1: Stabilize the Existing Project

Before adding features, make the current registration flow reliable.

### Tasks

- Correct model, import, URL configuration, serializer, response, and email-sending errors.
- Add `auth_app` and Django REST Framework to `INSTALLED_APPS`.
- Create and apply migrations for the custom user and verification models.
- Add a dependency file and an example environment configuration file.
- Configure email through environment variables.
- Prevent OTP values and other secrets from being printed or returned by the API.
- Add an expiry time, attempt count, used status, and purpose to OTP records.
- Hash OTP values in the database instead of storing them as plain text.
- Add unit and API tests for registration and OTP delivery.
- Add API documentation with request, response, and error examples.

### Deliverable

A working email registration endpoint with secure, expiring OTP verification and automated tests.

## 4. Phase 2: Create a Challenge and Verification System

Replace feature-specific OTP logic with a reusable challenge model and service.

### Suggested Models

#### `VerificationChallenge`

- `id`: UUID used as the public challenge identifier
- `user`: optional related user
- `target`: normalized email address or phone number
- `channel`: email, SMS, authenticator app, recovery code, or another method
- `purpose`: registration, login, password reset, email change, phone change, or MFA
- `secret_hash`: hashed verification code
- `expires_at`: challenge expiration time
- `attempt_count`: number of failed submissions
- `max_attempts`: maximum permitted submissions
- `used_at`: time of successful use
- `created_at`: creation time
- `metadata`: limited non-sensitive context

#### `AuthIdentity`

Connect one user to one or more login identities:

- Password identity
- Email identity
- Phone identity
- OAuth/OpenID Connect provider identity
- Passkey identity

#### `AuthEvent`

Record important events such as registration, login success, login failure, verification, password reset, MFA changes, session revocation, and CAPTCHA failure.

### Service Layer

Introduce services instead of placing business logic in views:

- `RegistrationService`
- `AuthenticationService`
- `ChallengeService`
- `NotificationService`
- `CaptchaService`
- `RiskService`
- `AuditService`

### Deliverable

A reusable verification engine used by registration, login, password recovery, and account changes.

## 5. Phase 3: Support Multiple Authentication Options

Implement each method behind a consistent API contract.

### Priority 1: Core Methods

- Email and password registration/login
- Email OTP verification
- Password reset using an expiring email challenge
- Refresh-token rotation and logout/session revocation
- Login history and active session management

### Priority 2: Passwordless and MFA

- Email magic-link login
- Email OTP login
- TOTP authenticator apps
- Single-use recovery codes
- Optional or required MFA policies
- Step-up authentication for sensitive actions

### Priority 3: Additional Identities

- Phone/SMS OTP after choosing and integrating an SMS provider
- Social login through OAuth 2.0/OpenID Connect
- Initial providers such as Google, GitHub, or Microsoft
- WebAuthn/passkeys for phishing-resistant authentication
- Account linking with protection against identity collisions and takeover

### Suggested API Groups

- `/api/v1/auth/register/`
- `/api/v1/auth/login/`
- `/api/v1/auth/logout/`
- `/api/v1/auth/token/refresh/`
- `/api/v1/auth/challenges/request/`
- `/api/v1/auth/challenges/verify/`
- `/api/v1/auth/password/forgot/`
- `/api/v1/auth/password/reset/`
- `/api/v1/auth/mfa/setup/`
- `/api/v1/auth/mfa/verify/`
- `/api/v1/auth/passkeys/`
- `/api/v1/auth/oauth/{provider}/start/`
- `/api/v1/auth/oauth/{provider}/callback/`
- `/api/v1/auth/sessions/`

## 6. Phase 4: Multi-CAPTCHA Architecture

Build CAPTCHA as a replaceable adapter rather than embedding one provider in each view.

### Supported CAPTCHA Categories

- Checkbox or interactive challenge CAPTCHA
- Invisible or score-based CAPTCHA
- Proof-of-work or privacy-focused CAPTCHA
- First-party image, text, or question challenges if a custom option is truly required

Custom visual CAPTCHAs should not be the default because accessibility, security, and bot resistance are difficult to maintain. Always provide an accessible alternative.

### Initial Provider Adapters

Start with two providers, then add more through the same interface:

- Cloudflare Turnstile
- Google reCAPTCHA
- hCaptcha
- A development-only fake provider for automated tests

Provider choices and their current terms, privacy behavior, regional availability, and SDK requirements must be reviewed before implementation.

### Common Provider Interface

Each adapter should implement behavior equivalent to:

```python
class CaptchaProvider:
    def verify(self, token, remote_ip=None, expected_action=None):
        """Return a normalized CaptchaResult."""
```

The normalized result should include:

- `success`
- `provider`
- `score`, when supported
- `action`, when supported
- `hostname`
- `error_codes`
- `verified_at`

### CAPTCHA Policy Engine

Do not require the same challenge for every request. Define policies by endpoint and risk level.

Example policies:

- Registration: always require CAPTCHA initially.
- Login: require CAPTCHA after repeated failures or suspicious activity.
- Password reset: require CAPTCHA before sending a recovery message.
- OTP resend: require CAPTCHA after repeated resend requests.
- Social login: require CAPTCHA only when risk signals justify it.
- Trusted sessions: skip CAPTCHA unless behavior changes significantly.

### Provider Selection and Failover

- Select the active provider through environment configuration.
- Allow different providers by deployment, tenant, country, or endpoint.
- Add a circuit breaker for provider outages.
- Use failover only when explicitly configured.
- Decide whether an outage should fail closed or fail open for each endpoint.
- Never silently bypass CAPTCHA on high-risk operations.
- Record provider latency and failure rates without storing raw CAPTCHA tokens.

### Example Configuration

```text
CAPTCHA_ENABLED=true
CAPTCHA_DEFAULT_PROVIDER=turnstile
CAPTCHA_FALLBACK_PROVIDER=hcaptcha
CAPTCHA_REGISTRATION_POLICY=always
CAPTCHA_LOGIN_POLICY=risk_based
CAPTCHA_PASSWORD_RESET_POLICY=always
```

Provider secrets must remain server-side. Site keys may be public and returned through a safe configuration endpoint if the frontend requires them.

### Backend Verification Flow

1. The frontend requests or renders a challenge for the configured provider.
2. The provider returns a short-lived token to the frontend.
3. The frontend includes that token and provider name in the authentication request.
4. The backend verifies the token directly with the provider.
5. The backend validates the action, hostname, score, token age, and replay rules where supported.
6. The policy engine accepts the request, rejects it, or requests an additional challenge.
7. The result is recorded as a security event without logging the raw token.

### Deliverable

A tested CAPTCHA abstraction with at least two real provider adapters, one fake test adapter, endpoint policies, observability, and documented frontend integration.

## 7. Phase 5: Risk-Based Security

Add a small risk engine so the system can increase protection only when necessary.

### Possible Signals

- Failed attempts for an account or IP address
- Request frequency and burst behavior
- New device or session
- Major geographic or network change
- Known proxy or data-center traffic, when legally and operationally appropriate
- Disposable email domain
- CAPTCHA result and score
- Recent password, email, phone, or MFA changes

### Possible Actions

- Allow the request
- Require CAPTCHA
- Require email or phone verification
- Require MFA or passkey verification
- Add a temporary cooldown
- Block and record the event

Begin with transparent rule-based decisions. Consider more advanced scoring only after sufficient reliable data exists.

## 8. Phase 6: Security and Privacy Hardening

- Use secure, HTTP-only, same-site cookies when browser clients use cookie-based sessions.
- If using JWTs, keep access tokens short-lived and rotate refresh tokens.
- Revoke sessions after password resets or suspected compromise.
- Apply Django password validators and consider breached-password checks.
- Use cryptographically secure random code generation through Python's `secrets` module.
- Enforce one-time use, expiry, resend cooldowns, and attempt limits for every challenge.
- Add throttling globally and per sensitive endpoint.
- Prevent account enumeration through response wording and timing controls.
- Validate redirect URIs and OAuth state/nonce values.
- Protect identity linking with recent authentication and explicit confirmation.
- Encrypt sensitive MFA secrets and minimize retained personal data.
- Define audit-log retention and deletion policies.
- Add security headers, strict CORS configuration, trusted hosts, and production HTTPS.
- Add dependency, secret, and static security scanning to CI.
- Create incident procedures for compromised keys and providers.

## 9. Phase 7: Testing Strategy

### Unit Tests

- User manager and model behavior
- Password and identity validation
- OTP generation, hashing, expiry, use, and attempt limits
- Each CAPTCHA provider's response normalization
- CAPTCHA and risk-policy decisions
- Token rotation and revocation

### API Tests

- Successful and failed flows for every authentication method
- Duplicate registration and account-enumeration resistance
- Expired, reused, malformed, or incorrect challenges
- CAPTCHA rejection, low scores, timeouts, and provider outages
- Rate limiting and lockout behavior
- Permission and session-revocation behavior

### Integration and Security Tests

- Mock external email, SMS, OAuth, and CAPTCHA services in CI.
- Run limited provider sandbox tests outside the normal unit-test suite.
- Test CSRF, CORS, replay, brute-force, open-redirect, and token-leak scenarios.
- Test accessibility for every interactive CAPTCHA option.

## 10. Phase 8: Operations and Deployment

- Use PostgreSQL in staging and production.
- Use Redis for throttling, challenge cooldowns, caching, and task queues.
- Send email and SMS asynchronously with a task worker.
- Add structured logs with request and correlation identifiers.
- Add metrics for authentication success, failures, lockouts, challenge delivery, CAPTCHA outcomes, latency, and provider availability.
- Alert on unusual failure spikes, abuse patterns, and external-provider outages.
- Document environment variables, migrations, backup, restore, and key rotation.
- Provide health and readiness endpoints that do not expose sensitive details.

## 11. Suggested Implementation Order

1. Repair and test the current email/password registration flow.
2. Implement the reusable verification challenge system.
3. Complete email verification and password reset.
4. Add login, refresh rotation, logout, and session management.
5. Add rate limiting and security event logging.
6. Create the CAPTCHA interface and fake provider.
7. Integrate Turnstile and one alternative provider.
8. Add endpoint-specific CAPTCHA policies and outage behavior.
9. Add TOTP MFA and recovery codes.
10. Add magic links and passwordless email login.
11. Add selected social-login providers.
12. Add passkeys/WebAuthn.
13. Add SMS only after reviewing cost, delivery, fraud, and recovery risks.
14. Add risk-based step-up authentication and production monitoring.

## 12. Definition of Done for Each Feature

A feature is complete only when it includes:

- Database migrations, if required
- Service-layer business logic
- API validation and consistent error responses
- Permission, abuse, and rate-limit rules
- Unit and API tests
- Audit events and operational metrics
- Environment configuration documentation
- API and frontend integration documentation
- Security and privacy review
- A rollback or provider-disable strategy

## 13. Recommended First Milestone

The first milestone should deliver a stable registration and verification foundation:

- Working custom user model and migrations
- Email/password registration
- Secure email OTP verification
- Resend cooldown and attempt limits
- Login and logout with revocable sessions
- CAPTCHA adapter interface
- Cloudflare Turnstile integration
- Fake CAPTCHA provider for tests
- Rate limits, audit events, and full automated test coverage for these flows

Completing this milestone creates a safe base for adding more authentication and CAPTCHA options without duplicating logic throughout the project.
