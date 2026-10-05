# Business Rules — U1 Walking Skeleton

Rules for the thin slice (sign-up → code → login → "who am I") and the groundwork policies every later unit relies on. Sources are requirement IDs (`requirements.md`), client IDs, team practices, and this unit's answers (`functional-design-questions.md` Q1–Q3).

```yaml
rules:
  # BR1 — Sign-up
  - id: BR1.1
    statement: Sign-up requires full name (1–120 chars after trimming), a valid email (≤254 chars) and a password.
    category: validation
    applies_to: User
    trigger: POST /auth/register
    logic: IF any field is missing or out of range THEN refuse with VALIDATION_FAILED and per-field details
    violation: 422 VALIDATION_FAILED, nothing stored
    source: FR2.1, FR-002
  - id: BR1.2
    statement: A password must have at least 8 characters, at least one letter and one number, at most 128 characters, and must not be on the common-password list.
    category: validation
    applies_to: User.passwordHash input
    trigger: sign-up (and later reset / change)
    logic: IF length < 8 OR length > 128 OR no letter OR no digit OR in common list THEN refuse naming the failed rule
    violation: 422 VALIDATION_FAILED with details.reason PASSWORD_TOO_WEAK
    source: stories Q14, AC3.1.4
  - id: BR1.3
    statement: An email that belongs to a verified account cannot sign up again.
    category: constraint
    applies_to: User.email
    trigger: POST /auth/register
    logic: IF a verified User has the same normalised email THEN refuse and send no code
    violation: 409 EMAIL_ALREADY_REGISTERED
    source: FR2.1, AC3.1.2
  - id: BR1.4
    statement: Signing up again with an email whose account is still unverified updates that account and sends a new code, subject to the resend cooldown.
    category: policy
    applies_to: User, OneTimeCode
    trigger: POST /auth/register with an unverified email
    logic: IF the existing User is unverified THEN replace fullName and passwordHash, supersede the live code, and issue a new one (unless within cooldown → 429)
    violation: 429 CODE_RESEND_COOLDOWN within 60 s of the last send
    source: AC3.1.3
  - id: BR1.5
    statement: Passwords are stored only as a slow adaptive salted hash; the plain password is never stored or logged.
    category: constraint
    applies_to: User.passwordHash
    trigger: any password write
    logic: hash with the configured algorithm and cost before persisting
    violation: n/a (enforced in code and tests)
    source: NFR2, AC3.1.5
  - id: BR1.6
    statement: Every new user has role "user".
    category: constraint
    applies_to: User.role
    trigger: user creation
    logic: role := user
    violation: n/a
    source: FR2.14, AUTH-009
  - id: BR1.7
    statement: Step 1 of sign-up or login never issues an access token or refresh cookie.
    category: policy
    applies_to: registration and login responses
    trigger: POST /auth/register, POST /auth/login
    logic: respond 202 with masked email and timing only
    violation: n/a
    source: AUTH-003, AC3.1.1, AC3.4.1

  # BR2 — One-time codes
  - id: BR2.1
    statement: Every one-time code is 6 random digits from a cryptographically secure source.
    category: policy
    applies_to: OneTimeCode
    trigger: code issue
    logic: code := 6 uniformly random digits (000000–999999)
    violation: n/a
    source: FD Q1, AUTH-015
  - id: BR2.2
    statement: Only a keyed hash of a code is stored; the plain code exists only in the outgoing email.
    category: constraint
    applies_to: OneTimeCode.codeHash
    trigger: code issue
    logic: store keyed hash; never log the code
    violation: n/a
    source: AUTH-011, AC3.2.5
  - id: BR2.3
    statement: A code is valid while now < issuedAt + 10 minutes; at exactly 10:00 it is expired.
    category: validation
    applies_to: OneTimeCode
    trigger: POST /auth/verify
    logic: IF now >= expiresAt THEN refuse as expired
    violation: 401 CODE_EXPIRED
    source: AUTH-011, AC3.2.1, AC3.2.2
  - id: BR2.4
    statement: A code can be used once.
    category: validation
    applies_to: OneTimeCode.consumedAt
    trigger: POST /auth/verify
    logic: IF consumedAt is set OR supersededAt is set THEN refuse
    violation: 401 CODE_INVALID
    source: AC3.2.3
  - id: BR2.5
    statement: A code is valid only for the purpose it was issued for.
    category: validation
    applies_to: OneTimeCode.purpose
    trigger: POST /auth/verify (and reset verify in U2)
    logic: look up only live codes with the requested purpose
    violation: 401 CODE_INVALID
    source: AC3.2.4
  - id: BR2.6
    statement: A new code for the same user and purpose can be sent only 60 seconds after the previous one, and supersedes it.
    category: policy
    applies_to: VerificationAttemptCounter.lastSentAt, OneTimeCode.supersededAt
    trigger: any code send
    logic: IF now < lastSentAt + 60 s THEN refuse ELSE supersede the live code and issue a new one
    violation: 429 CODE_RESEND_COOLDOWN with Retry-After
    source: AUTH-011, AC3.1.3
  - id: BR2.7
    statement: Wrong codes are counted per account and purpose; the 5th failure locks verification for 15 minutes, a resend does not reset the count, and a success resets it.
    category: policy
    applies_to: VerificationAttemptCounter
    trigger: POST /auth/verify
    logic: on wrong code failedCount += 1; IF failedCount >= 5 THEN lockedUntil := now + 15 min; while now < lockedUntil refuse all codes; on success failedCount := 0
    violation: 401 CODE_INVALID (with attemptsLeft) or 429 CODE_LOCKED
    source: AUTH-011, stories AC3.3.3
  - id: BR2.8
    statement: Responses that confirm a code was sent show the address partly hidden (first character, bullets, domain).
    category: policy
    applies_to: CodeSent response
    trigger: register, login, resend
    logic: maskedEmail := first char + "•••" + "@" + domain
    violation: n/a
    source: AC3.2.6

  # BR3 — Login
  - id: BR3.1
    statement: A failed password check returns the same error whether or not the email exists, after the same password-hash work.
    category: authorization
    applies_to: login
    trigger: POST /auth/login
    logic: IF user missing OR hash mismatch OR (user unverified) THEN INVALID_CREDENTIALS, after a dummy hash when the user is missing
    violation: 401 INVALID_CREDENTIALS
    source: AC3.4.2
  - id: BR3.2
    statement: A correct password sends a login code and issues no token.
    category: policy
    applies_to: login
    trigger: POST /auth/login success
    logic: issue OneTimeCode(purpose=login) per BR2.1–BR2.6, respond 202
    violation: n/a
    source: FR2.2, AC3.4.1
  - id: BR3.3
    statement: A verified code completes sign-up (sets isVerified) or login, returns an access token and sets the refresh cookie.
    category: policy
    applies_to: User, RefreshSession
    trigger: POST /auth/verify success
    logic: consume code; IF purpose=signup THEN isVerified := true, verifiedAt := now; create RefreshSession (new family); return access token + Set-Cookie
    violation: n/a
    source: FR2.3, AC3.2.1, AC3.4.3

  # BR4 — Tokens and identity
  - id: BR4.1
    statement: The access token is a signed token valid for 15 minutes carrying user id, role, issue and expiry times and a token type of "access".
    category: constraint
    applies_to: access token
    trigger: token issue
    logic: exp := iat + configured lifetime (15 min); signed with the configured key and algorithm
    violation: n/a
    source: AUTH-002, AUTH-012
  - id: BR4.2
    statement: The refresh token is delivered only as an httpOnly cookie valid for 7 days; the server stores its identifier and a hash of its secret, never the raw token.
    category: constraint
    applies_to: RefreshSession
    trigger: BR3.3
    logic: cookie refresh_token = tokenId.secret; HttpOnly; Max-Age = 7 days; Secure/SameSite/Path from configuration
    violation: n/a
    source: FE-002, AUTH-010, AUTH-012
  - id: BR4.3
    statement: Every route except the public allow-list requires a valid access token; missing, expired, tampered, unsigned ("none") and non-access tokens are refused.
    category: authorization
    applies_to: all protected routes
    trigger: every request
    logic: IF route not in public allow-list AND token invalid by signature, algorithm, expiry or type THEN refuse
    violation: 401 NOT_AUTHENTICATED
    source: FR2.10, AUTH-007, AC3.8.2
  - id: BR4.4
    statement: "Who am I" returns the signed-in user's id, full name, email, verification status, role and member-since date.
    category: policy
    applies_to: User
    trigger: GET /auth/me
    logic: read User by the token's user id
    violation: 401 NOT_AUTHENTICATED
    source: FR2.9, AC3.8.1

  # BR5 — Frontend session (U1 part)
  - id: BR5.1
    statement: The browser keeps the access token and user profile only in the in-memory auth store; nothing auth-related goes to Web Storage, and the store never persists.
    category: constraint
    applies_to: WebAuthClient
    trigger: sign-in
    logic: store in memory only
    violation: n/a (lint + test)
    source: FE-001, FE-002, AC1.9.1
  - id: BR5.2
    statement: Every frontend HTTP request goes through the single API client, which attaches the access token and sends credentials and X-Requested-With.
    category: constraint
    applies_to: WebAuthClient
    trigger: any request
    logic: client adds Authorization when a token exists, credentials include, X-Requested-With
    violation: n/a
    source: FE-004, AC1.9.2
  - id: BR5.3
    statement: UI components read auth state only through the store's selectors and never call auth endpoints or touch tokens.
    category: constraint
    applies_to: WebApp
    trigger: code review / lint
    logic: lint rule forbids imports of auth API modules and token access in components
    violation: CI failure
    source: FE-007, AC1.3.4, AC1.9.3
  - id: BR5.4
    statement: Until U2 adds session restore, reloading the page signs the user out; the refresh cookie is still set at sign-in.
    category: policy
    applies_to: WebAuthClient
    trigger: page reload
    logic: on load the store starts empty; protected pages route to log in
    violation: n/a
    source: FD Q3

  # BR6 — Safe handling of data and errors
  - id: BR6.1
    statement: Every error response uses the shared error format with a request id; no stack trace or internal detail reaches the client.
    category: policy
    applies_to: all endpoints
    trigger: any error
    logic: map typed errors to codes; unknown → 500 INTERNAL_ERROR with generic message
    violation: n/a
    source: contract C11, AC1.8.2
  - id: BR6.2
    statement: A request for a record owned by another user returns 404 and no data.
    category: authorization
    applies_to: user-owned records
    trigger: any owned-resource read or write
    logic: IF record.ownerUserId != current user THEN NOT_FOUND
    violation: 404 NOT_FOUND
    source: NFR3, AC1.8.1
  - id: BR6.3
    statement: Logs never contain passwords, codes, tokens, questionnaire answer text or image bytes.
    category: policy
    applies_to: logging
    trigger: any log write
    logic: structured logs with an allow-list of fields; redaction of known secret fields
    violation: test failure (canary check)
    source: NFR3, AC1.8.3

  # BR7 — Configuration and vendors
  - id: BR7.1
    statement: Every tunable value and secret is a typed configuration setting with a documented default or a required marker.
    category: policy
    applies_to: configuration
    trigger: start-up
    logic: settings loaded from environment / .env, validated at start
    violation: start-up refusal naming the setting
    source: NFR6, AC1.5.1
  - id: BR7.2
    statement: A vendor secret is required only when its real adapter is selected; with fakes selected none is needed.
    category: policy
    applies_to: configuration
    trigger: start-up
    logic: IF adapter = real AND secret missing THEN refuse to start (name only, never value)
    violation: start-up refusal
    source: AC1.5.2, AC1.5.3
  - id: BR7.3
    statement: Application source contains no literal API keys, prices or model names.
    category: policy
    applies_to: source code
    trigger: CI scan
    logic: secret scan + literal check
    violation: CI failure
    source: AC1.5.4
  - id: BR7.4
    statement: Email goes through an adapter chosen by configuration; every send has a timeout and failures are typed errors.
    category: policy
    applies_to: email sending
    trigger: code send
    logic: adapter by setting; timeout 10 s, 2 retries; error → UPSTREAM_UNAVAILABLE / UPSTREAM_TIMEOUT
    violation: 502 / 504
    source: NFR12, contract C10, AC1.6.1, AC1.6.2
  - id: BR7.5
    statement: The test email fake records sent codes for the test harness; production configuration cannot enable it.
    category: constraint
    applies_to: email fake
    trigger: tests
    logic: fake selectable only when environment is test or development
    violation: start-up refusal in production
    source: AC1.6.3
  - id: BR7.6
    statement: In local development, emails go to the local mail catcher.
    category: policy
    applies_to: email sending
    trigger: local run
    logic: SMTP adapter pointed at the mail catcher by default local configuration
    violation: n/a
    source: AC1.6.4, AC1.2.1

  # BR8 — Engineering policy (groundwork)
  - id: BR8.1
    statement: One repository holds two independent apps (backend, frontend), each with its own README and lockfile; neither imports the other.
    category: policy
    applies_to: repository
    trigger: every change
    logic: separate dependency manifests; cross-import check
    violation: CI failure
    source: NFR1, AC1.1.1, AC1.1.2
  - id: BR8.2
    statement: .gitignore excludes .env files (except .env.example), key files, Python caches and virtual environments, .next/ and local media folders.
    category: policy
    applies_to: repository
    trigger: commit
    logic: patterns present before the first commit
    violation: n/a
    source: AC1.1.3, practices Q9
  - id: BR8.3
    statement: Local development runs PostgreSQL and the mail catcher with Docker Compose, configured only from .env.example values.
    category: policy
    applies_to: local environment
    trigger: local setup
    logic: documented compose command
    violation: n/a
    source: NFR11, AC1.2.1
  - id: BR8.4
    statement: Schema changes ship only as Alembic migrations; upgrade, downgrade and upgrade again succeed in CI.
    category: policy
    applies_to: database
    trigger: every schema change
    logic: migration per change; CI round-trip check
    violation: CI failure
    source: NFR1, AC1.2.2, AC1.2.4
  - id: BR8.5
    statement: No hosting-provider SDK or host-specific configuration.
    category: constraint
    applies_to: codebase
    trigger: dependency change
    logic: dependency review
    violation: review rejection
    source: NFR11, AC1.2.3
  - id: BR8.6
    statement: Pull requests to main run lint, format, type, test and 80% coverage checks for both apps, and main is protected so failing checks block merging.
    category: policy
    applies_to: CI
    trigger: pull request
    logic: GitHub Actions workflow + branch protection
    violation: merge blocked
    source: NFR7, NFR8, AC1.3.1, AC1.3.2
  - id: BR8.7
    statement: The default test run cannot reach the network.
    category: policy
    applies_to: tests
    trigger: test run
    logic: backend sockets blocked; frontend unhandled requests fail
    violation: test failure
    source: AC1.3.3
  - id: BR8.8
    statement: Layering is lint-enforced: UI cannot import auth APIs or tokens; backend route handlers cannot import JWT/OTP internals.
    category: policy
    applies_to: codebase
    trigger: CI
    logic: ESLint restricted imports; backend import-linter contracts
    violation: CI failure
    source: Section 5.3, AC1.3.4, AC1.3.5
  - id: BR8.9
    statement: Secret scanning before commit, security lint rules, dependency audits and Dependabot are always on.
    category: policy
    applies_to: repository
    trigger: commit / CI
    logic: Gitleaks pre-commit; Ruff S; ESLint security plugins; pip-audit; npm audit; Dependabot
    violation: commit or CI blocked
    source: practices Q9, AC1.4.1–AC1.4.3
  - id: BR8.10
    statement: No authentication-as-a-service SDK may appear in either lockfile.
    category: constraint
    applies_to: dependencies
    trigger: CI
    logic: deny-list check on lockfiles
    violation: CI failure
    source: FR2.15, CON-002, AC1.4.4
```

## Rules summary

| Group | Rules | What they cover |
|---|---|---|
| BR1 Sign-up | BR1.1–BR1.7 | Input, password rule, unique verified email, re-sign-up, hashing, role, no early tokens |
| BR2 One-time codes | BR2.1–BR2.8 | 6 digits, hashed, 10-minute expiry, single use, purpose, 60 s cooldown, 5/15 lockout, masked email |
| BR3 Login | BR3.1–BR3.3 | Generic failure, code on success, tokens on verify |
| BR4 Tokens | BR4.1–BR4.4 | 15-min access token, 7-day httpOnly refresh, protected routes, who-am-I |
| BR5 Frontend session | BR5.1–BR5.4 | Memory-only store, single API client, selector-only UI, reload until U2 |
| BR6 Data safety | BR6.1–BR6.3 | Error format, 404 ownership, safe logs |
| BR7 Config and vendors | BR7.1–BR7.6 | Typed settings, secrets only when real, no literals, email adapter, fake, mail catcher |
| BR8 Engineering policy | BR8.1–BR8.10 | Repo shape, .gitignore, local env, migrations, host-neutral, CI, offline tests, layering, security tooling, no auth SaaS |
