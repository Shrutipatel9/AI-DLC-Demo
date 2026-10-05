# Security Requirements — U1 Walking Skeleton

**Scope:** the sign-up, code verification, login and "who am I" slice, plus the security groundwork every later unit inherits.

**Sources:** `requirements.md` NFR2, NFR3, NFR6; client `AUTH-001`–`AUTH-016`, `FE-001`–`FE-007`, `ASM-001`; `functional-design/rules.md` (BR*); answers Q3–Q5 in `nfr-requirements-questions.md`.

IDs extend the inception NFR they come from: NFR2.x is authentication security, NFR3.x is data protection, NFR6.x is secrets and configuration.

## 1. Authentication (NFR2)

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR2.1 | Authentication is custom and backend-controlled. No auth-as-a-service SDK is present (`AUTH-001`, `CON-002`). | Lockfile deny-list check fails CI if one appears (BR8.10). |
| NFR2.2 | Passwords are hashed with **Argon2id** using OWASP parameters (memory 19 MiB, 2 iterations, parallelism 1, 16-byte salt, 32-byte hash). The parameters are configurable, and hashes are re-hashed on login when the parameters change (Q3). | Unit test asserts the hash format prefix and parameters; no plaintext in the database or logs. |
| NFR2.3 | Password rule: 8–128 characters, at least one letter and one number, rejected if on a common-password list of ≥10,000 entries (BR1.2). | Table-driven tests at 7/8/128/129 characters and with a listed password. |
| NFR2.4 | Login timing does not reveal whether an email exists: a dummy Argon2id verification runs when the user is missing (BR3.1). | Test asserts the dummy verify path is executed; the response body and status are identical. |
| NFR2.5 | One-time codes: 6 digits from a CSPRNG; stored as HMAC-SHA-256 with a server key from configuration; expire at exactly 10:00; single use; purpose-bound; 60 s resend cooldown that supersedes the old code; 5 failures → 15-minute lock per account and purpose; resend never resets the count (BR2.1–BR2.7, `AUTH-011`). | Injectable-clock tests at T+9:59 / T+10:00, 59 s / 60 s, 4th / 5th failure, L+14:59 / L+15:00. |
| NFR2.6 | Access token: **HS256** JWT, 15-minute lifetime. Claims are `sub`, `role`, `iat`, `exp`, `typ=access` and `jti`, with a `kid` header so the key can be rotated (two keys accepted during rotation). Only HS256 is accepted; `none` and other algorithms are refused (Q4, BR4.1, BR4.3). | Tests for expiry at 14:59 / 15:00, a tampered signature, `alg:none`, a wrong `typ`, and an unknown `kid`. |
| NFR2.7 | Refresh cookie `refresh_token=<tokenId>.<secret>` is `HttpOnly`, `Max-Age` 7 days, with `Secure`/`SameSite`/`Path` from configuration. Defaults: `Path=/auth`, `SameSite=Lax`, `Secure` on outside local development. The server stores only the token id and a SHA-256 of the 32-byte random secret (BR4.2, `AUTH-010`). | Cookie attribute test; database inspection test shows no raw token. |
| NFR2.8 | Every non-public route requires a valid access token. The public allow-list is explicit and test-enumerated: `/health`, `/auth/register`, `/auth/login`, `/auth/verify`, plus U2's public auth routes when they exist. `/docs` and `/openapi.json` are disabled outside development (review R-05) (BR4.3). | Route-enumeration test: every route not in the allow-list returns 401 without a token. |
| NFR2.9 | **Per-IP throttling** on `/auth/register`, `/auth/login` and `/auth/verify`: by default 20 requests per minute per IP per endpoint (sliding window, configurable), returning 429 `RATE_LIMITED` with `Retry-After`. This is separate from the per-account code limits (Q5, review R-07). The client IP comes from the socket, or from a configured trusted-proxy header only. | Test: the 21st request within a minute gets 429; requests from another IP are unaffected. |
| NFR2.10 | Verification is atomic. Code consumption and the failure counter update happen in one transaction, with a row lock on the attempt counter, so parallel guesses cannot exceed 5 and one code cannot be consumed twice (functional design review R-01). | Concurrency test: 10 parallel wrong codes → exactly 5 counted, then locked; 2 parallel correct submissions → exactly one success. |

## 2. Authorisation and browser security (NFR2 continued)

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR2.11 | Role model: every user has role `user`. The role is carried in the token and checked by a reusable dependency (`AUTH-008`, `AUTH-009`). | Test that a token's role is read; no admin routes exist yet. |
| NFR2.12 | CORS allows only the configured frontend origin, with credentials. Allowed headers are `Authorization`, `Content-Type` and `X-Requested-With`; the exposed header is `Retry-After` (contract review R-07). | Preflight test from an allowed and a disallowed origin. |
| NFR2.13 | Security headers on API responses: `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` on `/auth/*`. The frontend sends a Content-Security-Policy that disallows inline scripts except Next.js nonces, plus `frame-ancestors 'none'` (`ASM-001` XSS hardening). | Header assertion tests (backend); a Playwright check of the CSP header (frontend). |
| NFR2.14 | The browser holds the access token in memory only. No auth data goes to `localStorage`, `sessionStorage` or `persist` (`FE-002`). | Vitest test of the store; a Playwright check that storage is empty after sign-in. |

## 3. Data protection (NFR3)

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR3.1 | Data classification for this unit: email and full name are **Confidential (PII)**; password hash, code hash, refresh secret hash and signing keys are **Restricted**. | Documented here; reviewed at the checkpoint. |
| NFR3.2 | Logs never contain passwords, codes, tokens, cookie values or full emails. Emails in logs are masked like the UI (`m•••@example.com`). This uses structured JSON logging with an allow-list of fields (BR6.3). | Canary test: seeded password, code and token never appear in captured logs. |
| NFR3.3 | Error responses never include stack traces or internal identifiers beyond `requestId` (BR6.1). | Test: a forced exception returns the generic `INTERNAL_ERROR` body. |
| NFR3.4 | Another user's record returns 404 (BR6.2). U1 has one owned resource ("who am I" for self); the reusable check is tested against a second user's id. | Unit test of the ownership dependency. |
| NFR3.5 | Transport: TLS is required outside local development. The backend refuses to start with `Secure=false` cookies when the environment is not `development` or `test`. | Start-up configuration test. |

## 4. Secrets and configuration (NFR6)

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR6.1 | `JWT_SIGNING_KEYS` (≥ 32 random bytes each, with `kid`), `CODE_HMAC_KEY` and database credentials come only from environment or `.env`. They are never committed, and `.env.example` holds placeholders (BR7.1–BR7.3). | Gitleaks pre-commit + CI; a start-up test refuses short or missing keys. |
| NFR6.2 | The email fake cannot be selected when `APP_ENV=production` (BR7.5). | Start-up test. |

## 5. Threat model (STRIDE) for this unit

| Threat | Example | Mitigation |
|---|---|---|
| Spoofing | Brute-force a login code | NFR2.5 lockout, NFR2.9 IP throttle, NFR2.10 atomicity |
| Spoofing | Forged access token | NFR2.6 HS256-only, `kid`, signature check |
| Tampering | Modified JWT claims | Signature verification; `typ` check |
| Repudiation | A user disputes sign-ups | INFO logs of auth events (user id, event, request id); see observability |
| Information disclosure | Email enumeration through sign-up or login | NFR2.4 generic login failure. Sign-up's "already registered" is client-accepted (`FR2.1`); throttled by NFR2.9 |
| Information disclosure | Secrets in the repo or logs | NFR3.2, NFR6.1, Gitleaks |
| Denial of service | Argon2 cost abuse through mass login | NFR2.9 throttle; bounded request body size (16 KB on `/auth/*`) |
| Elevation of privilege | Using a reset token as an access token (later) | NFR2.6 `typ` claim check |

## 6. Compliance notes
Email and name are personal data. Health and biometric data are not processed in this unit. The jurisdiction question (GDPR and others) stays open with the client (requirements Q2), and the consent step arrives in U3. No retention feature is built (client §2.2).
