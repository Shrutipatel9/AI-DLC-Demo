# Backend API (FastAPI)

Python 3.12 · FastAPI · SQLAlchemy 2 (synchronous) · Alembic · PostgreSQL 16 · uv

## Setup

```bash
docker compose up -d --wait postgres mailpit     # from the repository root
cp .env.example .env                             # fill in the placeholders (keys: openssl rand -base64 48)
uv sync
uv run python -m tools.fetch_face_model          # the pinned face model, once (U4)
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload --port 8000
```

The app is created by a factory (`app.main:create_app`), so uvicorn needs `--factory`.
Start-up fails fast, with a message naming the problem, when the configuration is invalid,
the database is unreachable, migrations are not at head, or the pinned face model is missing
or is not the pinned version (`FACE_MODEL_PRELOAD`).

## Commands

| Task | Command |
|---|---|
| Lint / format | `uv run ruff check .` · `uv run ruff format .` |
| Types | `uv run mypy --strict app` |
| Layering contracts | `uv run lint-imports` |
| Face model and test portrait (once; hash-checked, git-ignored `var/models/`) | `uv run python -m tools.fetch_face_model` |
| Tests (needs `source ../scripts/ci-env.sh`, Compose and the face model) | `uv run pytest tests/platform tests/identity tests/health tests/onboarding tests/media tests/face tests/photos tests/payments -m "not perf" --cov=app --cov-fail-under=80` |
| Photo tests only (U4) | `uv run pytest tests/photos tests/media tests/face -q` |
| Payment tests only (U5; the Stripe fake, never Stripe) | `uv run pytest tests/payments -q` |
| Re-render the synthetic face fixtures (only when the renderer or model pin changes) | `uv run python -m tools.make_face_fixtures --out tests/fixtures/faces --out ../frontend/e2e/fixtures/photos` |
| Latency checks and anti-enumeration timing | `uv run pytest -m perf tests/identity/test_perf_auth.py tests/health/test_perf_health.py tests/identity/test_perf_sessions.py tests/identity/test_perf_enumeration.py` |
| Identity clean-up (old sessions, reset tokens, shadow counters) | `uv run python -m app.identity.cleanup` |
| New migration | `uv run alembic revision --autogenerate -m "<unit>_<change>"`, then review it |
| Migration round-trip (throwaway DB) | `uv run alembic -x db=e2e upgrade head && uv run alembic -x db=e2e downgrade base && uv run alembic -x db=e2e upgrade head` |
| OpenAPI document | `uv run python -m tools.export_openapi openapi.json` |

Tests use a real PostgreSQL database (`app_test`, created and migrated automatically), never
SQLite. Network access is blocked except to localhost (`pytest-socket`), and email uses a
recording fake and payments use the Stripe fake, so no test can call a paid or outside
service. The photo tests run the real
MediaPipe model on committed synthetic face renders (`tests/fixtures/faces`, no real person)
and on MediaPipe's own sample portrait, which `tools.fetch_face_model` downloads.

## Environment keys

Every value comes from the environment or `.env` (`app/platform/settings.py`). Secrets are
required and have no default; the start-up error names a bad setting but never prints its value.

| Key | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | `development`, `test`, `staging`, `production`. `/docs` and `/openapi.json` exist only in development |
| `LOG_LEVEL` | `INFO` | JSON logs on stdout |
| `DATABASE_URL` | required | `postgresql+psycopg://user:pass@127.0.0.1:5432/app` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT` / `DB_POOL_RECYCLE` | 5 / 5 / 5 s / 1800 s | |
| `CHECK_MIGRATIONS_AT_STARTUP` | `true` | |
| `FRONTEND_ORIGIN` | required | The web app origin (normalised to `scheme://host[:port]`) |
| `CSRF_ALLOWED_ORIGINS` | value of `FRONTEND_ORIGIN` | Comma-separated. The Origin/Referer allow-list on `/auth/refresh` and `/auth/logout`, and the CORS allow-list. No wildcard |
| `TRUSTED_PROXIES` | empty | Comma-separated; only these may set `X-Forwarded-For` |
| `AUTH_MAX_BODY_BYTES` | 16384 | Larger `/auth/*` bodies get 422 `BODY_TOO_LARGE` |
| `JWT_SIGNING_KEYS` | required | JSON `{"kid": "<base64 >= 32 bytes>"}`; several keys allow rotation |
| `JWT_ACTIVE_KID` | required | The kid that signs new tokens |
| `ACCESS_TOKEN_TTL_SECONDS` | 900 | 15 minutes |
| `CODE_HMAC_KEY` | required | base64, >= 32 bytes; keyed hash of one-time codes |
| `CODE_TTL_SECONDS` / `CODE_RESEND_COOLDOWN_SECONDS` | 600 / 60 | |
| `CODE_MAX_FAILURES` / `CODE_LOCK_SECONDS` | 5 / 900 | |
| `REFRESH_TOKEN_DAYS` | 7 | Lifetime of each refresh session from its own issue (every rotation issues a fresh one) |
| `REFRESH_ATTEMPT_RECOVERY_SECONDS` | 60 | How long a lost refresh response can be recovered with the same `X-Refresh-Attempt` id |
| `REFRESH_COOKIE_NAME` / `_DOMAIN` | `refresh_token` / unset | |
| `REFRESH_COOKIE_PATH` | `/auth` | Must be `/auth` (start-up refuses anything else): it covers refresh, logout and change-password |
| `REFRESH_COOKIE_SAMESITE` | `lax` | `lax`, `strict` or `none`. `none` (cross-site deployments) requires `REFRESH_COOKIE_SECURE=true` |
| `RESET_TOKEN_MINUTES` | 10 | Lifetime of the single-use password-reset token |
| `EMAIL_HASH_KEY` | required | base64, >= 32 bytes; keyed hash for the anti-enumeration shadow counters. The `.env.example` placeholder is refused on purpose |
| `REFRESH_COOKIE_SECURE` | `true` | `false` only for development/test (start-up refuses otherwise) |
| `ARGON2_MEMORY_KIB` / `ARGON2_TIME_COST` / `ARGON2_PARALLELISM` | 19456 / 2 / 1 | OWASP Argon2id minimum; old hashes are upgraded at login |
| `EMAIL_BACKEND` | `smtp` | `smtp` or `fake` (`fake` is refused outside development/test) |
| `EMAIL_FROM`, `SMTP_HOST`, `SMTP_PORT` | `no-reply@localhost`, `127.0.0.1`, 1025 | Mailpit locally |
| `SMTP_USERNAME` / `SMTP_PASSWORD` / `SMTP_STARTTLS` | empty / empty / `false` | STARTTLS is required outside development/test |
| `EMAIL_TIMEOUT_SECONDS` / `EMAIL_SEND_BUDGET_SECONDS` / `EMAIL_MAX_ATTEMPTS` | 10 / 25 / 3 | Per-attempt timeout, total budget, attempts |
| `EMAIL_MAX_CONCURRENCY` | 10 | Email bulkhead size |
| `AUTH_EMAIL_HOURLY_CAP` | 500 | Global cap on code emails per hour (503 above it) |
| `RATE_LIMIT_BACKEND` | `postgres` | `memory` only for development/test |
| `AUTH_RATE_LIMIT_PER_MINUTE` / `AUTH_RATE_LIMIT_WINDOW_SECONDS` | 20 / 60 | Per IP, per auth endpoint (register, login, verify, resend-code, password/*, change-password) |
| `REFRESH_RATE_LIMIT_PER_MINUTE` | 60 | Per IP, for `/auth/refresh` and `/auth/logout` (many tabs behind one NAT). `scripts/ci-env.sh` raises both limits for test servers only |
| `METRICS_ENABLED` / `METRICS_ALLOW_CIDRS` | `false` / `127.0.0.1/32` | `/metrics` (Prometheus) for allow-listed clients only |
| `ONBOARDING_CONSENT_FILE` | bundled `app/onboarding/data/consent_v1.json` | JSON `{version, text, agreement}`. A new text needs a new `version`; users then consent again |
| `ONBOARDING_QUESTIONNAIRE_FILE` | bundled `app/onboarding/data/questionnaire_v1.json` | The questionnaire definition ([QS] 23 questions). Invalid files stop start-up. A stored version is immutable: publish changes under a new `version` |
| `ONBOARDING_SUPPORT_URL` | empty | Optional `https://` professional-support link for the "I can't confirm" message. None is invented |
| `MEDIA_BACKEND` | `local` | Private file storage behind the FileStorage port; only local disk exists until a host is chosen |
| `MEDIA_ROOT` | `var/media` | Private directory for stored photos (git-ignored). Never served as static files: only `GET /media/{fileId}` reads it, for the owner |
| `FACE_MODEL_PATH` | `var/models/face_landmarker.task` | The pinned MediaPipe Face Landmarker (`face_landmarker/float16/1`, SHA-256 in `app/face/model.py`) |
| `FACE_MODEL_PRELOAD` | `true` | Load and hash-check the model at start-up (once per process) |
| `FACE_LANDMARK_OVERRIDES_FILE` | empty | Development/test only (refused otherwise): recorded landmarks for E2E fixture images, see `app/face/overrides.py` |
| `PHOTO_ANGLES` | `front,left_3q,right_3q` | The required angles, in order (ASM-005). Each must exist in the catalog |
| `PHOTO_CATALOG_FILE` | bundled `app/photos/data/catalog_v1.json` | Rules, guidance and angles (labels, instructions, pose ranges) |
| `PHOTO_POSE_YAW_RANGES` | empty | Optional JSON `{"angle": [min, max]}` in degrees, overriding the catalog's pose ranges |
| `PHOTO_MAX_UPLOAD_BYTES` | `10485760` | Upload limit (413 `PHOTO_TOO_LARGE`) |
| `PHOTO_MAX_DIMENSION` | `2048` | Stored photos are downscaled so the longer side is at most this |
| `PHOTO_MIN_WIDTH` / `PHOTO_MIN_HEIGHT` | `480` / `480` | Minimum resolution |
| `PHOTO_MIN_BRIGHTNESS` / `PHOTO_MAX_BRIGHTNESS` | `60` / `230` | Mean luminance (0-255) of the face region |
| `PHOTO_MIN_FACE_FRACTION` / `PHOTO_MAX_FACE_FRACTION` | `0.05` / `0.8` | Face landmark box as a share of the image area |
| `PHOTO_OCCLUSION_DARK_RATIO` / `PHOTO_OCCLUSION_MIN_CONTRAST` | `0.35` / `0.06` | Covered eyes/mouth heuristic, relative to the cheeks |
| `IDENTITY_THRESHOLD` | `0.6` | Same-person threshold (ASM-010): a pair matches when its signature distance is <= this |
| `REPORT_PRICE_AMOUNT` | required | The report price in minor units (cents): `2900` is 29.00. The price is still open (OQ-002), so it is never in code (FR-016) |
| `REPORT_PRICE_CURRENCY` | required | ISO 4217 code such as `USD` (stored upper-case) |
| `PAYMENT_PROVIDER` | `stripe` | `stripe` (hosted Checkout) or `fake` (a local test checkout page; refused outside development/test) |
| `STRIPE_SECRET_KEY` | required for `stripe` | Use a test-mode key (`sk_test_...`) locally. Never commit it |
| `STRIPE_WEBHOOK_SECRET` | required for `stripe` | The endpoint's signing secret (`whsec_...`); the Stripe CLI prints one for local forwarding. The fake signs with it when set |
| `STRIPE_TIMEOUT_SECONDS` / `STRIPE_MAX_NETWORK_RETRIES` | 10 / 1 | Per-call timeout and SDK retries (contract section 6) |
| `PAYMENT_SUCCESS_URL` / `PAYMENT_CANCEL_URL` | `FRONTEND_ORIGIN` + `/payment/success` / `/payment/cancel` | Where Checkout sends the user back |
| `PAYMENT_CONFIRM_WAIT_SECONDS` | 30 | After this wait the confirming screen says the payment is still being confirmed |
| `FAKE_PAYMENT_BASE_URL` / `FAKE_PAYMENT_WEBHOOK_DELAY_SECONDS` | `http://localhost:8000` / 2 | Fake only: this API's public URL (test page and webhook target) and the delay before it posts the signed webhook |

The per-photo thresholds are initial values set during development (`ASM-002`, US5.9); they
are configuration, so the client's Photo Validation Specification values can be loaded
without a code change.

## Layer map

```text
app/
  main.py                 composition root: create_app(), lifespan, route classes
  health/routes.py        /health (liveness), /health/ready (database)
  identity/               sign-up, codes, login, tokens, sessions, password reset/change
    routes.py             HTTP handlers (thin): register, login, verify, me, resend-code,
                          refresh, logout, password/forgot, password/verify-code,
                          password/reset, change-password
    dependencies.py       current_user (Bearer token), require_owner (404), require_role
    services.py           IdentityService: workflows and resend; composes the U2 services
    cleanup.py            `python -m app.identity.cleanup` maintenance command
    password_reset.py     forgot -> verify code -> reset (non-revealing, single-use token)
    password_change.py    change password; keeps this session's family, revokes the rest
    sessions.py           refresh sessions: rotation, reuse detection, recovery, revocation
    shadow.py             email-keyed shadow counters for unknown emails
    delivery.py           sending codes after the response (background task, own session)
    codes.py              OTP service: 6-digit codes, HMAC, expiry, cooldown, lockout
    tokens.py             JWT service: HS256 with kid rotation
    passwords.py          Argon2id hasher and the password rule (10k common list)
    cookies.py            refresh cookie value and attributes
    repositories.py       SQL for users, codes, counters, refresh sessions
    models.py             ORM models
    schemas.py            request and response models (camelCase JSON)
    public.py             the only module other packages may import
  onboarding/             consent and the branching questionnaire (U3; ADR-007)
    routes.py             HTTP handlers (thin): /onboarding/consent, /questionnaire,
                          /response, /response/answers/{questionId}, /response/submit
    dependencies.py       service lookup; Cache-Control: no-store on every response
    services.py           consent gate, save answer, submit (required + disclaimer checks),
                          non-medical read port
    repositories.py       SQL for consent records, definition versions, responses
    definition.py         seed loader and validation, branching (showIf), answer checks
    models.py             ORM models
    schemas.py            request and response models (no medical flag is ever sent)
    data/                 consent_v1.json, questionnaire_v1.json (from [QS])
    public.py             build_onboarding, router, get_non_medical_answers,
                          get_onboarding_state, require_submitted_questionnaire
  media/                  MediaStore: private files behind the FileStorage port (U4; C8)
    routes.py             GET /media/{fileId}: owner-checked (404 otherwise), no-store
    services.py           MediaStore: put, get (owner check), retire + purge, discard
    images.py             type from the bytes; decode, upright, RGB, downscale, re-encode
                          (no EXIF/GPS/device data; HEIC -> JPEG; PNG stays PNG)
    storage.py            FileStorage port and the local-disk adapter (atomic writes)
    repositories.py  models.py  dependencies.py
    public.py             build_media_store, router, prepare_photo, decode_stored
  face/                   FaceGeometry: the one MediaPipe Face Landmarker (U4; US1.11)
    geometry.py           FaceFound (478 landmarks, yaw) | NoFace | MultipleFaces; the port
    mediapipe_landmarker.py  the adapter: model loaded once per process, results never cached
    model.py              the pin (version, URL, SHA-256) and its check
    overrides.py          development/test landmark overrides for E2E fixtures
    public.py             build_face_geometry and the result types
  photos/                 PhotoIntake: requirements, upload, checks, same-person (U4; C4)
    routes.py             HTTP handlers (thin): GET /photos/requirements, GET /photos,
                          PUT /photos/{angle}; no-store; questionnaire must be submitted
    services.py           upload (size, type, re-encode, detect, checks, replace),
                          photo_set, evaluate_identity (fresh every call), snapshot_for_run
    checks.py             per-photo checks and their reason codes
    identity.py           5-ratio signature, L1 distance, the same-person decision
    catalog.py            the photo catalog loader (configured angles, pose ranges)
    repositories.py  models.py  schemas.py  dependencies.py
    data/catalog_v1.json  rules, guidance and angles ([PC] §1-§3)
    public.py             build_photos, router, check_identity, snapshot_for_run,
                          get_photo_set_state
  payments/               Payments: offer, hosted Checkout, webhook, paywall (U5; C2, C5)
    routes.py             HTTP handlers (thin): GET /payments/offer, POST /payments/checkout,
                          GET /payments/status (no-store, protected); POST
                          /payments/stripe/webhook (public, signature over the raw body)
    services.py           offer, start_checkout (ALREADY_PAID, then the same-person re-check),
                          handle_webhook (verify, record the event id once, apply), status,
                          entitlement, require_paid (402)
    gateway.py            the PaymentGateway port, Stripe-format signing and verification,
                          event parsing
    stripe_gateway.py     Stripe adapter (SDK; one-time payment mode, inline price data,
                          idempotency key, 10 s timeout, 1 retry)
    fake_gateway.py       the fake provider (development/test) and its webhook deliverer
    fake_routes.py        the fake's hosted test page (/payments/fake-checkout/*)
    repositories.py  models.py  schemas.py  dependencies.py
    public.py             build_payment_gateway, build_payments, routers, entitlement,
                          payment_state, require_paid, paid_photo_snapshot
  platform/               shared infrastructure (never imports feature modules)
    settings.py  db.py  errors.py  logging.py  request_id.py  middleware.py
    ratelimit.py  retry.py  clock.py  metrics.py  routing.py
    email/                port, SMTP adapter, recording fake, dispatcher (bulkhead), templates
alembic/                  migrations (one history; files named by unit)
tools/export_openapi.py   OpenAPI document for frontend type generation
tools/fetch_face_model.py the pinned face model and the sample test portrait
tools/make_face_fixtures.py  synthetic face renders for tests and the browser journey
```

Dependency direction (enforced by import-linter in CI): `routes -> dependencies -> services |
cleanup -> password_reset | password_change -> sessions | shadow | delivery -> codes | tokens |
passwords | cookies -> repositories -> models`. Route handlers never import the JWT or OTP
services, the shadow counters or the repositories directly. `platform` (which also holds the
CSRF check, `platform/csrf.py`) never imports `identity` or `health`. Outside `identity`, code
imports only `app.identity.public`.

Onboarding (U3): `public -> routes -> dependencies -> services -> repositories -> definition ->
models`. Outside `onboarding`, code imports only `app.onboarding.public`, and the only way
answers leave the module is `get_non_medical_answers`, which never returns a medical-flagged
answer (Q8-Q12) or its follow-up (ADR-007).

Media, face and photos (U4): `media.public -> routes -> dependencies -> services ->
repositories | storage | images -> models`; `face.public -> overrides | mediapipe_landmarker
-> geometry | model`; `photos.public -> routes -> dependencies -> services -> repositories |
checks | identity -> catalog | models`. Outside each module only its `public` module is
imported.

Payments (U5): `public -> routes | fake_routes -> dependencies -> services -> repositories |
stripe_gateway | fake_gateway -> gateway | models`. Route handlers never import the
repositories, the models or the Stripe adapter. Outside `payments`, code imports only
`app.payments.public`.

## Payments (U5)

- **Offer** (`GET /payments/offer`): `REPORT_PRICE_AMOUNT` (minor units) and
  `REPORT_PRICE_CURRENCY` from configuration, plus what payment unlocks.
- **Checkout** (`POST /payments/checkout`, 201 `{checkoutUrl}`): 409 `ALREADY_PAID` after a
  successful payment; then the same-person re-check from the photos stored now (409
  `PHOTO_SET_INCOMPLETE`, or 409 `PHOTO_IDENTITY_MISMATCH` naming the angles the U4 check
  flags). A `pending` payment is committed before Stripe is called (outside any
  transaction); a Stripe failure marks the attempt `failed` and answers 502/504, nothing charged.
- **Webhook** (`POST /payments/stripe/webhook`, public): the `Stripe-Signature` header is
  checked against the raw body with the Stripe SDK verifier (400, nothing changes, when it
  fails). The event id is recorded first under a unique constraint, so a repeated or
  concurrent delivery is processed once. `checkout.session.completed` (paid) and
  `async_payment_succeeded` mark the payment `succeeded`; `async_payment_failed` and `expired`
  mark a pending one `failed`. It answers 200 only after the commit and never starts analysis.
- **Status** (`GET /payments/status`): `none` / `pending` / `paid` and `confirmWaitSeconds`,
  polled by the confirming screen. It changes only through the webhook, never the redirect.
- **Paywall** (`app.payments.public`): `require_paid` raises 402 `PAYMENT_REQUIRED`;
  `paid_photo_snapshot` checks payment first (402) and then the photo set (409), the order
  "Start Analysis" (U6) and the report (U8) must use.
- **The fake provider** (`PAYMENT_PROVIDER=fake`, development/test only, also used by the
  test suite and the browser journeys): `POST /payments/checkout` returns
  `/payments/fake-checkout/{sessionId}` on this API, a small test page with "Pay" and
  "Cancel". "Pay" posts a `checkout.session.completed` event, signed in Stripe's format with
  `STRIPE_WEBHOOK_SECRET` (or a random per-process secret), to the webhook after
  `FAKE_PAYMENT_WEBHOOK_DELAY_SECONDS`, and sends the browser to the success URL. "Cancel"
  sends it to the cancel URL; nothing is charged.

### Local testing with real Stripe (test mode)

1. In `.env`: `PAYMENT_PROVIDER=stripe` and `STRIPE_SECRET_KEY=sk_test_...` (a test-mode key).
2. Forward webhooks with the [Stripe CLI](https://docs.stripe.com/stripe-cli):
   `stripe listen --forward-to localhost:8000/payments/stripe/webhook`. It prints a signing
   secret; put it in `STRIPE_WEBHOOK_SECRET` and restart the API.
3. Pay on the hosted page with a Stripe test card (for example `4242 4242 4242 4242`, any
   future date, any CVC). The CLI forwards `checkout.session.completed` and the confirming
   screen turns to "confirmed".

The default test run never calls Stripe: the tests use the fake, and the Stripe adapter is
tested with the SDK's HTTP layer stubbed.

## Photos (U4)

- **Upload** (`PUT /photos/{angle}`, multipart `file` + optional `captureMethod`): size (413),
  type from the bytes (415), decode (422 `UNREADABLE`), then the per-photo checks. A failing
  photo answers 422 `PHOTO_REJECTED` with one `{angle, reason}` per failed check and is never
  stored. If the angle already has an accepted photo it is kept; otherwise the angle shows
  `rejected` with its reasons. An accepted photo replaces the angle's photo, and the old file
  is deleted after the commit.
- **Per-photo checks** (`app/photos/checks.py`): `TOO_SMALL`, `NO_FACE`, `MULTIPLE_FACES`,
  `TOO_DARK`, `TOO_BRIGHT`, `FACE_TOO_SMALL`, `FACE_TOO_LARGE`, `POSE_MISMATCH` (head yaw from
  the face transformation matrix against the angle's range) and `EYES_COVERED` /
  `MOUTH_COVERED` (a first-pass heuristic: the region is much darker or flatter than the
  cheeks). The browser turns each code into a photo-focused fix.
- **Same-person check** (`app/photos/identity.py`): for each photo, five widths (eye, nose,
  mouth, jaw, face) divided by the inter-eye distance; a pair matches when the sum of absolute
  differences is <= `IDENTITY_THRESHOLD`. The largest group of matching photos is kept and the
  rest are flagged; front is kept when no pair agrees, and in the hub case the side farther
  from front is flagged (equal distances flag right). `evaluate_identity` re-reads and
  re-measures the stored photos on every call; nothing is cached. `GET /photos`, every
  accepted upload, and the C4 port (`check_identity`, `snapshot_for_run`) all use it.
- **Calibration** (US5.9): the threshold and the per-photo values have been checked only
  against the synthetic fixtures and one real sample portrait. They must be calibrated on real
  photos of real people before handover.

### Questionnaire content

The questions, options, branching rule (Q19 shown when Q4 is Masculine or No Preference),
follow-ups (Q9, Q11), medical flags and the disclaimer are data in
`app/onboarding/data/questionnaire_v1.json`; no code change is needed to edit them. Items still
open with the client are labelled `[Open — client]` in that file. Each answer is stored with
its question id, question text and medical flag.

## Session model (U2)

- **Refresh sessions.** Signing in starts a *family*. The httpOnly cookie
  `refresh_token=<tokenId>.<secret>` (Path `/auth`) is exchanged at `POST /auth/refresh` for a
  new 15-minute access token and a new cookie; the old session is marked rotated and a child is
  created in the same family. Only `sha256(secret)` is stored; secrets are compared in constant
  time. Each exchange locks the parent row (`FOR UPDATE`), so two concurrent exchanges of one
  cookie give one child.
- **Strict reuse detection.** Presenting an already-rotated session revokes the whole family
  (`reuse_detected`) and answers 401 `SESSION_INVALID` with reason `REUSE_DETECTED`.
- **Lost-response recovery.** The web app sends a random `X-Refresh-Attempt` id (22 base64url
  characters) per refresh; its SHA-256 is stored on the child. The same id within
  `REFRESH_ATTEMPT_RECOVERY_SECONDS`, while the child is unused, re-issues that child instead
  of counting as reuse. A stolen cookie has no attempt id.
- **Revocation** (logout, reset, change) is lock-then-update: lock the scope's usable rows,
  then update in a new statement, so a refresh in flight is always caught. Logout revokes the
  cookie's whole family; a reset revokes every session; a change keeps the caller's family.
- **CSRF.** `/auth/refresh` and `/auth/logout` require `X-Requested-With: XMLHttpRequest` and an
  allow-listed `Origin` (or `Referer`); otherwise 403 `CSRF_CHECK_FAILED` before the cookie is
  read. CORS is the outermost middleware, with the same allow-list.
- **Anti-enumeration.** `/auth/password/forgot` and `/auth/resend-code` (purposes `login` and
  `password_reset`) do the same work for every email and always answer 202 with the same body;
  the code is issued and emailed by a background task after the response. Unknown emails count
  wrong codes on email-keyed shadow counters, so they lock after five tries like real accounts.
- **Clean-up.** `uv run python -m app.identity.cleanup` deletes sessions expired, rotated or
  revoked more than 30 days ago, reset tokens used or expired more than 30 days ago, and shadow
  counters idle for a day. It is idempotent (batches of 1,000, `SKIP LOCKED`). There is no
  scheduler yet: run it by hand; a host scheduler should run it daily once hosting exists.

## Errors

Every non-2xx response is `{"error": {"code", "message", "details", "requestId"}}`
(contract C11). The `X-Request-ID` header matches `requestId` and every log line for the
request. Stack traces go to the logs only.
