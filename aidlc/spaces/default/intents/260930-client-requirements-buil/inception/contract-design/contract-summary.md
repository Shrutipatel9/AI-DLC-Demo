# Contract Summary — AI Facial Analysis Platform

These are the formal contracts the system must honour. They cover the public HTTP API between the browser and the backend, the Stripe webhook, and the in-process interfaces between backend modules that different units build.

**Sources:**
- `inception/units-generation/unit-of-work.md` and `unit-of-work-dependency.md`
- `inception/domain-design/components.md` and `decisions.md`
- `inception/requirements-analysis/requirements.md`
- `inception/user-stories/stories.md`
- the client-stated endpoints in `client_requirements.md` §5
- answers Q1–Q6 in `contract-design-questions.md`

**Conventions decided here:**
- No URL version prefix; the client's `/auth/*` paths are kept exactly (Q1).
- One error format with a fixed code list (Q2).
- camelCase JSON (Q3).
- Polling for live status (Q4).
- Whole chat replies, not streamed (Q5).
- OpenAPI-generated frontend types, checked in CI (Q6).

## 1. Contracts

| # | Provider Unit | Consumer | Mechanism | Owner |
|---|---|---|---|---|
| C1 | Backend app (U1–U10, per path group below) | External: web frontend (browser, Next.js app) | REST/HTTP JSON (OpenAPI 3.1) | Each path group is owned by the unit that builds its module; the document as a whole by U1 |
| C2 | U5 Payments | External: Stripe (webhook caller) | HTTPS webhook | U5 |
| C3 | U1/U2 Identity | All backend units | In-process auth dependency | U1 |
| C4 | U4 PhotoIntake | U5 Payments, U6 AnalysisPipeline, U10 Journey | In-process interface | U4 |
| C5 | U5 Payments | U6 AnalysisPipeline, U8 Report, U10 Journey | In-process interface | U5 |
| C6 | U3 Onboarding | U6 ReportWriting (via pipeline), U9 BeautyAssistant, U10 Journey | In-process interface | U3 |
| C7 | U6 AnalysisPipeline | U6 FaceMeasurement / ReportWriting, U7 ImageGeneration, U8 Report | In-process step hook | U6 (defines); providers register |
| C8 | U4 MediaStore | U4, U6, U7, U8 | In-process interface | U4 |
| C9 | U8 Report | U9 BeautyAssistant, U10 Journey | In-process read interface | U8 |
| C10 | Owning modules (U1, U5, U6, U7) | Vendor adapters (email, Stripe, OpenAI text, image, storage) | In-process ports | Owning unit |
| C11 | Shared | All units | Shared error format and error codes | U1 |

Direction note (architecture review R-03 of Units Generation): C7 is defined by U6, and U7 **registers** its image step into it. The code dependency therefore runs U7 → U6, matching the unit graph.

---

## 2. C11 — Error format and error codes (shared schema)

Every non-2xx response from C1 uses this body. The frontend branches only on `code`, never on `message`.

```yaml
# shared-schema: ErrorResponse
ErrorResponse:
  type: object
  required: [error]
  properties:
    error:
      type: object
      required: [code, message, requestId]
      properties:
        code: { type: string, description: "One value from the ErrorCode list" }
        message: { type: string, description: "Plain-language text safe to show a user" }
        details:
          type: array
          items:
            type: object
            properties:
              field: { type: string, description: "Input field, for 422" }
              reason: { type: string }
              angle: { type: string, description: "Photo angle, for photo errors" }
        requestId: { type: string, description: "Correlates with server logs; no personal data" }
ErrorCode:
  type: string
  enum:
    - VALIDATION_FAILED          # 422 input shape or rule (for example PASSWORD_TOO_WEAK in details)
    - NOT_AUTHENTICATED          # 401 missing, expired or invalid access token
    - SESSION_INVALID            # 401 refresh cookie missing, expired, revoked or reused (frontend clears auth)
    - CSRF_CHECK_FAILED          # 403 X-Requested-With or Origin/Referer not allowed
    - INVALID_CREDENTIALS        # 401 wrong email or password (never says which)
    - EMAIL_ALREADY_REGISTERED   # 409 sign-up with a verified email
    - CODE_INVALID               # 401 wrong code; details carries attemptsLeft
    - CODE_EXPIRED               # 401 code older than 10 minutes
    - CODE_LOCKED                # 429 5 failures; Retry-After = seconds to lockout end
    - CODE_RESEND_COOLDOWN       # 429 resend within 60 s; Retry-After = seconds left
    - RESET_TOKEN_INVALID        # 401 reset token expired, used or wrong type
    - CONSENT_REQUIRED           # 403 questionnaire action before consent
    - DISCLAIMER_REQUIRED        # 422 submit without the disclaimer
    - QUESTIONNAIRE_NOT_SUBMITTED # 409 step needs a submitted questionnaire
    - PHOTO_REJECTED             # 422 per-photo check failed; details = reasons
    - PHOTO_TOO_LARGE            # 413 over 10 MB
    - PHOTO_UNSUPPORTED_TYPE     # 415 not JPEG, PNG or HEIC
    - PHOTO_SET_INCOMPLETE       # 409 not all angles accepted
    - PHOTO_IDENTITY_MISMATCH    # 409 same-person check failed; details = mismatched angles (BR-005 rule 8)
    - PAYMENT_REQUIRED           # 402 no successful payment (FR-015)
    - ALREADY_PAID               # 409 checkout after a successful payment
    - ANALYSIS_ALREADY_COMPLETE  # 409 start after a completed run
    - RERUN_NOT_AVAILABLE        # 409 free re-run used or run not failed
    - REPORT_NOT_READY           # 404 no published report yet
    - NOT_FOUND                  # 404 missing or owned by another user (never 403, to hide existence)
    - IMAGE_RETRY_LIMIT_REACHED  # 429 3 manual retries used for this image
    - CHAT_DAILY_LIMIT_REACHED   # 429 daily limit hit; Retry-After = seconds to 00:00 UTC
    - UPSTREAM_UNAVAILABLE       # 502 OpenAI, image vendor, Stripe or email failed after retries
    - UPSTREAM_TIMEOUT           # 504 same, by timeout
    - INTERNAL_ERROR             # 500 unexpected; message is generic
```

**Precedence when several apply:**
1. `NOT_AUTHENTICATED`
2. `PAYMENT_REQUIRED` (402)
3. `PHOTO_IDENTITY_MISMATCH` (409)
4. other state errors

This follows stories AC6.4.2.

---

## 3. C1 — Public HTTP API (OpenAPI 3.1)

Every endpoint except the public ones (`/auth/register`, `/auth/login`, `/auth/verify`, `/auth/resend-code`, `/auth/password/*`, `/auth/refresh`, `/payments/stripe/webhook`, `/health`) requires `Authorization: Bearer <accessToken>`. The frontend sends every request with `credentials: include` and `X-Requested-With: XMLHttpRequest`. CORS allows only the configured frontend origin, with credentials.

```yaml
openapi: 3.1.0
info:
  title: AI Facial Analysis Platform API
  version: 1.0.0
  description: >
    Public HTTP API consumed by the Next.js frontend. Paths without a version prefix (contract Q1).
    JSON is camelCase (Q3). Errors use ErrorResponse (C11). The refresh token travels only in the
    httpOnly cookie `refresh_token`; it never appears in a body.
servers:
  - url: "{apiBaseUrl}"
    variables:
      apiBaseUrl: { default: "http://localhost:8000", description: "Set by configuration; no host assumed (NFR-010)" }
security:
  - bearerAuth: []
tags:
  - { name: auth, description: "U1/U2 Identity" }
  - { name: onboarding, description: "U3 Onboarding" }
  - { name: photos, description: "U4 PhotoIntake" }
  - { name: payments, description: "U5 Payments" }
  - { name: analysis, description: "U6 AnalysisPipeline" }
  - { name: images, description: "U7 ImageGeneration" }
  - { name: report, description: "U8 Report" }
  - { name: chat, description: "U9 BeautyAssistant" }
  - { name: journey, description: "U10 Journey" }
  - { name: media, description: "U4 MediaStore" }
paths:
  /health:
    get:
      tags: [journey]
      security: []
      summary: Liveness check
      responses:
        "200": { description: OK, content: { application/json: { schema: { type: object, properties: { status: { const: ok } } } } } }

  # ---------------- auth (U1: register, verify, login, me; U2: the rest) ----------------
  /auth/register:
    post:
      tags: [auth]
      security: []
      summary: Step 1 of sign-up — creates an unverified user and emails a code (AUTH-003)
      requestBody:
        required: true
        content: { application/json: { schema: { $ref: "#/components/schemas/RegisterRequest" } } }
      responses:
        "202": { description: Code sent, content: { application/json: { schema: { $ref: "#/components/schemas/CodeSent" } } } }
        "409": { $ref: "#/components/responses/Error" }   # EMAIL_ALREADY_REGISTERED (verified account)
        "422": { $ref: "#/components/responses/Error" }   # VALIDATION_FAILED (password rule, email)
        "429": { $ref: "#/components/responses/Error" }   # CODE_RESEND_COOLDOWN when re-registering an unverified email
  /auth/login:
    post:
      tags: [auth]
      security: []
      summary: Step 1 of login — checks the password and emails a code; issues no token
      requestBody:
        required: true
        content: { application/json: { schema: { $ref: "#/components/schemas/LoginRequest" } } }
      responses:
        "202": { description: Code sent, content: { application/json: { schema: { $ref: "#/components/schemas/CodeSent" } } } }
        "401": { $ref: "#/components/responses/Error" }   # INVALID_CREDENTIALS
        "429": { $ref: "#/components/responses/Error" }   # CODE_LOCKED
  /auth/verify:
    post:
      tags: [auth]
      security: []
      summary: Step 2 — verifies the emailed code; on success returns the access token and sets the refresh cookie
      requestBody:
        required: true
        content: { application/json: { schema: { $ref: "#/components/schemas/VerifyRequest" } } }
      responses:
        "200":
          description: Signed in
          headers:
            Set-Cookie: { $ref: "#/components/headers/RefreshCookie" }
          content: { application/json: { schema: { $ref: "#/components/schemas/SessionResponse" } } }
        "401": { $ref: "#/components/responses/Error" }   # CODE_INVALID (details.attemptsLeft) | CODE_EXPIRED
        "429": { $ref: "#/components/responses/Error" }   # CODE_LOCKED
  /auth/resend-code:
    post:
      tags: [auth]
      security: []
      summary: Sends a new code and invalidates the previous one (60 s cooldown)
      requestBody:
        required: true
        content: { application/json: { schema: { $ref: "#/components/schemas/ResendRequest" } } }
      responses:
        "202": { description: Code sent, content: { application/json: { schema: { $ref: "#/components/schemas/CodeSent" } } } }
        "429": { $ref: "#/components/responses/Error" }   # CODE_RESEND_COOLDOWN | CODE_LOCKED
  /auth/refresh:
    post:
      tags: [auth]
      security: [refreshCookie: []]
      summary: Exchanges the refresh cookie for a new access token and rotates the cookie (AUTH-012)
      parameters:
        - { $ref: "#/components/parameters/XRequestedWith" }
      responses:
        "200":
          description: Refreshed
          headers:
            Set-Cookie: { $ref: "#/components/headers/RefreshCookie" }
          content: { application/json: { schema: { $ref: "#/components/schemas/AccessToken" } } }
        "401": { $ref: "#/components/responses/Error" }   # SESSION_INVALID (reuse revokes the whole family)
        "403": { $ref: "#/components/responses/Error" }   # CSRF_CHECK_FAILED
  /auth/logout:
    post:
      tags: [auth]
      security: [refreshCookie: []]
      summary: Revokes the refresh session and clears the cookie
      parameters:
        - { $ref: "#/components/parameters/XRequestedWith" }
      responses:
        "204":
          description: Logged out
          headers:
            Set-Cookie: { description: "refresh_token cleared (Max-Age=0)", schema: { type: string } }
        "403": { $ref: "#/components/responses/Error" }   # CSRF_CHECK_FAILED
  /auth/me:
    get:
      tags: [auth]
      summary: The signed-in user (AUTH-014)
      responses:
        "200": { description: Current user, content: { application/json: { schema: { $ref: "#/components/schemas/User" } } } }
        "401": { $ref: "#/components/responses/Error" }
  /auth/password/forgot:
    post:
      tags: [auth]
      security: []
      summary: Requests a reset code; always the same response (anti-enumeration, BR-009 exception)
      requestBody:
        required: true
        content: { application/json: { schema: { type: object, required: [email], properties: { email: { type: string, format: email } } } } }
      responses:
        "202": { description: "Same response whether or not the account exists" }
  /auth/password/verify-code:
    post:
      tags: [auth]
      security: []
      summary: Verifies the 6-digit reset code and returns a single-use reset token (AUTH-015)
      requestBody:
        required: true
        content: { application/json: { schema: { type: object, required: [email, code], properties: { email: { type: string, format: email }, code: { type: string, pattern: "^[0-9]{6}$" } } } } }
      responses:
        "200": { description: Reset token, content: { application/json: { schema: { $ref: "#/components/schemas/ResetToken" } } } }
        "401": { $ref: "#/components/responses/Error" }   # CODE_INVALID | CODE_EXPIRED
        "429": { $ref: "#/components/responses/Error" }   # CODE_LOCKED
  /auth/password/reset:
    post:
      tags: [auth]
      security: []
      summary: Sets the new password with the reset token; revokes every session of the account
      requestBody:
        required: true
        content: { application/json: { schema: { type: object, required: [resetToken, newPassword], properties: { resetToken: { type: string }, newPassword: { type: string } } } } }
      responses:
        "204": { description: Password changed; all sessions revoked }
        "401": { $ref: "#/components/responses/Error" }   # RESET_TOKEN_INVALID
        "422": { $ref: "#/components/responses/Error" }   # VALIDATION_FAILED (password rule)
  /auth/change-password:
    post:
      tags: [auth]
      summary: In-session password change; the current session stays valid (AUTH-016)
      requestBody:
        required: true
        content: { application/json: { schema: { type: object, required: [currentPassword, newPassword], properties: { currentPassword: { type: string }, newPassword: { type: string } } } } }
      responses:
        "204": { description: Changed }
        "401": { $ref: "#/components/responses/Error" }   # INVALID_CREDENTIALS (wrong current password)
        "422": { $ref: "#/components/responses/Error" }

  # ---------------- onboarding (U3) ----------------
  /onboarding/consent:
    get:
      tags: [onboarding]
      summary: Current consent text and whether the user has consented
      responses:
        "200": { description: Consent state, content: { application/json: { schema: { $ref: "#/components/schemas/ConsentState" } } } }
    post:
      tags: [onboarding]
      summary: Records consent to the given text version (FR4.1)
      requestBody:
        required: true
        content: { application/json: { schema: { type: object, required: [consentTextVersion], properties: { consentTextVersion: { type: string } } } } }
      responses:
        "201": { description: Recorded, content: { application/json: { schema: { $ref: "#/components/schemas/ConsentState" } } } }
        "409": { $ref: "#/components/responses/Error" }   # stale text version
  /onboarding/questionnaire:
    get:
      tags: [onboarding]
      summary: The active questionnaire definition (questions, options, branching, disclaimer text)
      responses:
        "200": { description: Definition, content: { application/json: { schema: { $ref: "#/components/schemas/QuestionnaireDefinition" } } } }
        "403": { $ref: "#/components/responses/Error" }   # CONSENT_REQUIRED
  /onboarding/response:
    get:
      tags: [onboarding]
      summary: The user's saved answers and progress
      responses:
        "200": { description: Response, content: { application/json: { schema: { $ref: "#/components/schemas/QuestionnaireProgress" } } } }
        "403": { $ref: "#/components/responses/Error" }
  /onboarding/response/answers/{questionId}:
    put:
      tags: [onboarding]
      summary: Saves or changes one answer; returns the recalculated visible questions (branching)
      parameters:
        - { name: questionId, in: path, required: true, schema: { type: string } }
      requestBody:
        required: true
        content: { application/json: { schema: { $ref: "#/components/schemas/AnswerInput" } } }
      responses:
        "200": { description: Saved, content: { application/json: { schema: { $ref: "#/components/schemas/QuestionnaireProgress" } } } }
        "403": { $ref: "#/components/responses/Error" }   # CONSENT_REQUIRED
        "409": { $ref: "#/components/responses/Error" }   # already submitted
        "422": { $ref: "#/components/responses/Error" }
  /onboarding/response/submit:
    post:
      tags: [onboarding]
      summary: Submits the questionnaire; refused without the disclaimer (BR-003)
      requestBody:
        required: true
        content: { application/json: { schema: { type: object, required: [disclaimerConfirmed], properties: { disclaimerConfirmed: { type: boolean, const: true } } } } }
      responses:
        "200": { description: Submitted, content: { application/json: { schema: { $ref: "#/components/schemas/QuestionnaireProgress" } } } }
        "422": { $ref: "#/components/responses/Error" }   # DISCLAIMER_REQUIRED | VALIDATION_FAILED (unanswered required)

  # ---------------- photos (U4) ----------------
  /photos:
    get:
      tags: [photos]
      summary: Required angles, each photo's status, and a freshly computed same-person result
      responses:
        "200": { description: Photo set, content: { application/json: { schema: { $ref: "#/components/schemas/PhotoSet" } } } }
        "409": { $ref: "#/components/responses/Error" }   # QUESTIONNAIRE_NOT_SUBMITTED
  /photos/{angle}:
    put:
      tags: [photos]
      summary: Uploads or replaces the photo for one angle; runs the per-photo checks
      parameters:
        - { name: angle, in: path, required: true, schema: { type: string, description: "One of the configured requiredAngles" } }
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema: { type: object, required: [file], properties: { file: { type: string, format: binary }, captureMethod: { type: string, enum: [upload, camera] } } }
      responses:
        "200": { description: Accepted; returns the whole set (identity recomputed), content: { application/json: { schema: { $ref: "#/components/schemas/PhotoSet" } } } }
        "413": { $ref: "#/components/responses/Error" }   # PHOTO_TOO_LARGE
        "415": { $ref: "#/components/responses/Error" }   # PHOTO_UNSUPPORTED_TYPE
        "422": { $ref: "#/components/responses/Error" }   # PHOTO_REJECTED, details[].reason per failed check

  # ---------------- payments (U5) ----------------
  /payments/offer:
    get:
      tags: [payments]
      summary: Price, currency and what payment unlocks (from configuration)
      responses:
        "200": { description: Offer, content: { application/json: { schema: { $ref: "#/components/schemas/Offer" } } } }
  /payments/checkout:
    post:
      tags: [payments]
      summary: Creates a Stripe hosted Checkout session after the same-person re-check
      responses:
        "201": { description: Checkout created, content: { application/json: { schema: { type: object, required: [checkoutUrl], properties: { checkoutUrl: { type: string, format: uri } } } } } }
        "409": { $ref: "#/components/responses/Error" }   # PHOTO_IDENTITY_MISMATCH | PHOTO_SET_INCOMPLETE | ALREADY_PAID
  /payments/status:
    get:
      tags: [payments]
      summary: Payment state for the confirming screen (polled every 2–3 s, Q4)
      responses:
        "200": { description: State, content: { application/json: { schema: { $ref: "#/components/schemas/PaymentStatus" } } } }
  /payments/history:
    get:
      tags: [payments]
      summary: Billing history for Settings
      responses:
        "200": { description: History, content: { application/json: { schema: { type: array, items: { $ref: "#/components/schemas/PaymentRecord" } } } } }

  # ---------------- analysis (U6) ----------------
  /analysis/runs:
    post:
      tags: [analysis]
      summary: "Start Analysis" — idempotent; a second call returns the same run (AC7.1.3)
      responses:
        "202": { description: Run started or already running, content: { application/json: { schema: { $ref: "#/components/schemas/AnalysisRun" } } } }
        "402": { $ref: "#/components/responses/Error" }   # PAYMENT_REQUIRED (checked first)
        "409": { $ref: "#/components/responses/Error" }   # PHOTO_IDENTITY_MISMATCH | ANALYSIS_ALREADY_COMPLETE
  /analysis/runs/current:
    get:
      tags: [analysis]
      summary: The current run's steps and state (polled every 2–3 s)
      responses:
        "200": { description: Run, content: { application/json: { schema: { $ref: "#/components/schemas/AnalysisRun" } } } }
        "404": { $ref: "#/components/responses/Error" }
  /analysis/runs/current/rerun:
    post:
      tags: [analysis]
      summary: The one free re-run after a failed run (stories Q8)
      responses:
        "202": { description: Re-run started, content: { application/json: { schema: { $ref: "#/components/schemas/AnalysisRun" } } } }
        "409": { $ref: "#/components/responses/Error" }   # RERUN_NOT_AVAILABLE

  # ---------------- images (U7) ----------------
  /images:
    get:
      tags: [images]
      summary: All 24 image slots for the user's report (AI Visuals and per-feature)
      responses:
        "200": { description: Slots, content: { application/json: { schema: { type: array, items: { $ref: "#/components/schemas/ImageSlot" } } } } }
        "402": { $ref: "#/components/responses/Error" }
  /images/{imageId}/retry:
    post:
      tags: [images]
      summary: Manual retry of a failed image (max 3 per image, stories Q10)
      parameters:
        - { name: imageId, in: path, required: true, schema: { type: string, format: uuid } }
      responses:
        "202": { description: Retry queued, content: { application/json: { schema: { $ref: "#/components/schemas/ImageSlot" } } } }
        "404": { $ref: "#/components/responses/Error" }
        "409": { $ref: "#/components/responses/Error" }   # slot not in failed state
        "429": { $ref: "#/components/responses/Error" }   # IMAGE_RETRY_LIMIT_REACHED

  # ---------------- report (U8) ----------------
  /report:
    get:
      tags: [report]
      summary: The published report — template sections, assessments, 11 features, recommendations, image slot refs
      responses:
        "200": { description: Report, content: { application/json: { schema: { $ref: "#/components/schemas/Report" } } } }
        "402": { $ref: "#/components/responses/Error" }
        "404": { $ref: "#/components/responses/Error" }   # REPORT_NOT_READY
  /report/dashboard:
    get:
      tags: [report]
      summary: Home dashboard data ([RD] §4)
      responses:
        "200": { description: Dashboard, content: { application/json: { schema: { $ref: "#/components/schemas/Dashboard" } } } }
        "402": { $ref: "#/components/responses/Error" }
        "404": { $ref: "#/components/responses/Error" }
  /report/pdf:
    get:
      tags: [report]
      summary: The report PDF — generated on first request, cached, regenerated when an image changed
      responses:
        "200": { description: PDF, content: { application/pdf: { schema: { type: string, format: binary } } } }
        "202": { description: "Being generated; retry after Retry-After seconds", headers: { Retry-After: { schema: { type: integer } } } }
        "402": { $ref: "#/components/responses/Error" }
        "404": { $ref: "#/components/responses/Error" }

  # ---------------- chat (U9) ----------------
  /chat/messages:
    get:
      tags: [chat]
      summary: Conversation history and today's remaining messages
      responses:
        "200": { description: Conversation, content: { application/json: { schema: { $ref: "#/components/schemas/ChatState" } } } }
        "404": { $ref: "#/components/responses/Error" }   # REPORT_NOT_READY
    post:
      tags: [chat]
      summary: Sends a message; returns the whole reply (Q5)
      requestBody:
        required: true
        content: { application/json: { schema: { type: object, required: [text], properties: { text: { type: string, minLength: 1, maxLength: 2000 } } } } }
      responses:
        "200": { description: Reply, content: { application/json: { schema: { $ref: "#/components/schemas/ChatReply" } } } }
        "429": { $ref: "#/components/responses/Error" }   # CHAT_DAILY_LIMIT_REACHED (Retry-After to 00:00 UTC)
        "502": { $ref: "#/components/responses/Error" }   # UPSTREAM_UNAVAILABLE (does not count toward the limit)
        "504": { $ref: "#/components/responses/Error" }

  # ---------------- journey (U10) ----------------
  /journey/next-step:
    get:
      tags: [journey]
      summary: The user's next unfinished step (US11.8)
      responses:
        "200": { description: Next step, content: { application/json: { schema: { $ref: "#/components/schemas/NextStep" } } } }

  # ---------------- media (U4) ----------------
  /media/{fileId}:
    get:
      tags: [media]
      summary: Owner-checked private file (photo, generated image); never public
      parameters:
        - { name: fileId, in: path, required: true, schema: { type: string, format: uuid } }
      responses:
        "200": { description: File bytes, content: { image/jpeg: { schema: { type: string, format: binary } }, image/png: { schema: { type: string, format: binary } } } }
        "404": { $ref: "#/components/responses/Error" }   # missing or not yours

components:
  securitySchemes:
    bearerAuth: { type: http, scheme: bearer, bearerFormat: JWT, description: "15-minute access token (AUTH-012)" }
    refreshCookie: { type: apiKey, in: cookie, name: refresh_token, description: "httpOnly, rotated on every use, 7 days" }
  parameters:
    XRequestedWith:
      name: X-Requested-With
      in: header
      required: true
      schema: { type: string, const: XMLHttpRequest }
      description: CSRF defence together with the Origin/Referer allow-list (AUTH-013)
  headers:
    RefreshCookie:
      description: "refresh_token=<opaque>; HttpOnly; Max-Age=604800; Secure/SameSite/Path from configuration"
      schema: { type: string }
  responses:
    Error:
      description: Error (see C11)
      content: { application/json: { schema: { $ref: "#/components/schemas/ErrorResponse" } } }
  schemas:
    ErrorResponse:
      type: object
      required: [error]
      properties:
        error:
          type: object
          required: [code, message, requestId]
          properties:
            code: { type: string }
            message: { type: string }
            details: { type: array, items: { type: object, additionalProperties: true } }
            requestId: { type: string }
    RegisterRequest:
      type: object
      required: [fullName, email, password]
      properties:
        fullName: { type: string, minLength: 1, maxLength: 120 }
        email: { type: string, format: email, maxLength: 254 }
        password: { type: string, minLength: 8, maxLength: 128, description: "Letter + number; common passwords rejected" }
    LoginRequest:
      type: object
      required: [email, password]
      properties:
        email: { type: string, format: email }
        password: { type: string }
    VerifyRequest:
      type: object
      required: [email, code, purpose]
      properties:
        email: { type: string, format: email }
        code: { type: string, pattern: "^[0-9]{6}$" }
        purpose: { type: string, enum: [signup, login] }
    ResendRequest:
      type: object
      required: [email, purpose]
      properties:
        email: { type: string, format: email }
        purpose: { type: string, enum: [signup, login, password_reset] }
    CodeSent:
      type: object
      required: [maskedEmail, resendAvailableAt, expiresAt]
      properties:
        maskedEmail: { type: string, examples: ["m•••@example.com"] }
        resendAvailableAt: { type: string, format: date-time }
        expiresAt: { type: string, format: date-time }
    AccessToken:
      type: object
      required: [accessToken, expiresAt]
      properties:
        accessToken: { type: string }
        expiresAt: { type: string, format: date-time }
    SessionResponse:
      allOf:
        - $ref: "#/components/schemas/AccessToken"
        - type: object
          required: [user]
          properties: { user: { $ref: "#/components/schemas/User" } }
    ResetToken:
      type: object
      required: [resetToken, expiresAt]
      properties:
        resetToken: { type: string, description: "Single use; rejected as a Bearer token" }
        expiresAt: { type: string, format: date-time }
    User:
      type: object
      required: [id, fullName, email, isVerified, role, memberSince]
      properties:
        id: { type: string, format: uuid }
        fullName: { type: string }
        email: { type: string, format: email }
        isVerified: { type: boolean }
        role: { type: string, enum: [user] }
        memberSince: { type: string, format: date-time }
    ConsentState:
      type: object
      required: [consentTextVersion, consentText, given]
      properties:
        consentTextVersion: { type: string }
        consentText: { type: string }
        given: { type: boolean }
        givenAt: { type: [string, "null"], format: date-time }
    QuestionnaireDefinition:
      type: object
      required: [definitionVersion, questions, disclaimerText]
      properties:
        definitionVersion: { type: string }
        disclaimerText: { type: string }
        questions:
          type: array
          items:
            type: object
            required: [id, order, text, type]
            properties:
              id: { type: string }
              order: { type: integer }
              text: { type: string }
              type: { type: string, enum: [text, single, multi, yesno] }
              options: { type: array, items: { type: object, properties: { value: { type: string }, label: { type: string }, group: { type: string } } } }
              required: { type: boolean }
              showIf: { type: object, description: "Branching rule: { questionId, anyOf: [values] }" }
              followUp: { type: object, description: "{ showWhen: value, type: text, label }" }
          description: "The medical flag is NOT exposed to the client; it is used server-side only (ADR-007)"
    AnswerInput:
      type: object
      required: [value]
      properties:
        value: { description: "string | string[] | boolean depending on question type" }
        followUpText: { type: [string, "null"], maxLength: 2000 }
    QuestionnaireProgress:
      type: object
      required: [answers, visibleQuestionIds, submitted]
      properties:
        answers: { type: object, additionalProperties: true, description: "questionId → value (the user's own answers)" }
        visibleQuestionIds: { type: array, items: { type: string } }
        submitted: { type: boolean }
        submittedAt: { type: [string, "null"], format: date-time }
    PhotoSet:
      type: object
      required: [requiredAngles, photos, identity]
      properties:
        requiredAngles: { type: array, items: { type: string }, examples: [["front", "left_3q", "right_3q"]] }
        photos:
          type: array
          items:
            type: object
            required: [angle, status]
            properties:
              angle: { type: string }
              status: { type: string, enum: [missing, accepted, rejected] }
              reasons: { type: array, items: { type: string } }
              imageUrl: { type: [string, "null"], description: "/media/{fileId}" }
        identity:
          type: object
          required: [status, mismatchedAngles]
          properties:
            status: { type: string, enum: [incomplete, consistent, mismatch] }
            mismatchedAngles: { type: array, items: { type: string } }
    Offer:
      type: object
      required: [amount, currency, includes]
      properties:
        amount: { type: integer, description: "Minor units, from configuration (FR-016)" }
        currency: { type: string, examples: ["USD"] }
        includes: { type: array, items: { type: string } }
    PaymentStatus:
      type: object
      required: [state]
      properties:
        state: { type: string, enum: [none, pending, paid] }
        paidAt: { type: [string, "null"], format: date-time }
    PaymentRecord:
      type: object
      required: [date, amount, currency, status]
      properties:
        date: { type: string, format: date-time }
        amount: { type: integer }
        currency: { type: string }
        status: { type: string, enum: [pending, succeeded, failed] }
    AnalysisRun:
      type: object
      required: [runId, status, steps, rerunAvailable]
      properties:
        runId: { type: string, format: uuid }
        status: { type: string, enum: [running, completed, failed] }
        steps:
          type: array
          items:
            type: object
            required: [key, state]
            properties:
              key: { type: string, enum: [measuring, writing, generating_images, assembling] }
              state: { type: string, enum: [done, current, waiting, failed] }
        rerunAvailable: { type: boolean }
        failureMessage: { type: [string, "null"], description: "Plain language, never a raw error" }
    ImageSlot:
      type: object
      required: [imageId, slotKind, slotKey, status, manualRetriesLeft]
      properties:
        imageId: { type: string, format: uuid }
        slotKind: { type: string, enum: [feature_after, hairstyle, outfit, aging] }
        slotKey: { type: string, examples: ["nose", "hairstyle_3", "aging_plus_5"] }
        status: { type: string, enum: [pending, ready, failed] }
        imageUrl: { type: [string, "null"] }
        manualRetriesLeft: { type: integer, minimum: 0, maximum: 3 }
        aiGenerated: { type: boolean, const: true }
    Report:
      type: object
      required: [reportId, publishedAt, templateSections, assessments, features, recommendations]
      properties:
        reportId: { type: string, format: uuid }
        publishedAt: { type: string, format: date-time }
        templateSections: { type: object, properties: { understandingYourResults: { type: string }, introduction: { type: string }, limitations: { type: string } } }
        assessments:
          type: object
          properties:
            symmetry: { type: object, properties: { score: { type: integer, minimum: 0, maximum: 100 }, label: { type: string }, regionalBalance: { type: array, items: { type: object } } } }
            facialThirds: { type: object, properties: { upper: { type: number }, middle: { type: number }, lower: { type: number } } }
            dimorphism: { type: object, additionalProperties: true }
            prototypicality: { type: [number, "null"] }
            faceShape: { type: [string, "null"] }
        features:
          type: array
          minItems: 11
          maxItems: 11
          items:
            type: object
            required: [key, narrative, summary, potentialIdeas, metrics, beforeImageUrl, afterImageId]
            properties:
              key: { type: string, enum: [hair, eyebrows, eyes, nose, cheeks, jaw, lips, chin, skin, neck, ears] }
              narrative: { type: string }
              potentialIdeas: { type: array, items: { type: string } }
              summary: { type: string }
              metrics: { type: array, items: { type: object, properties: { name: { type: string }, value: { type: [number, "null"] }, unit: { type: string } } } }
              noMeasurementReason: { type: [string, "null"] }
              beforeImageUrl: { type: string }
              afterImageId: { type: string, format: uuid }
        recommendations:
          type: object
          required: [atHome, overTheCounter, inClinic, professionalAdviceText]
          properties:
            atHome: { type: array, items: { type: string } }
            overTheCounter: { type: array, items: { type: string } }
            inClinic: { type: array, items: { type: string } }
            professionalAdviceText: { type: string }
    Dashboard:
      type: object
      description: "Home dashboard ([RD] §4); items marked TBD in [RD] are omitted until decided"
      properties:
        overallScore: { type: [integer, "null"] }
        evaluatedPoints: { type: [integer, "null"] }
        analysisDurationSeconds: { type: [integer, "null"] }
        priorityFeatures: { type: array, items: { type: object, properties: { key: { type: string }, score: { type: integer }, label: { type: string }, attributes: { type: array, items: { type: object } } } } }
        harmonyProfile: { type: array, items: { type: object, properties: { axis: { type: string }, value: { type: [number, "null"] } } }, minItems: 6, maxItems: 6 }
        protocol: { type: array, items: { type: object } }
        facialAge: { type: [integer, "null"] }
        beforeImageUrl: { type: string }
        potentialImageId: { type: [string, "null"] }
        reportStatus: { type: string, enum: [ready] }
    ChatState:
      type: object
      required: [messages, remainingToday, resetsAt]
      properties:
        messages: { type: array, items: { type: object, properties: { role: { type: string, enum: [user, assistant] }, text: { type: string }, createdAt: { type: string, format: date-time } } } }
        remainingToday: { type: integer, minimum: 0 }
        resetsAt: { type: string, format: date-time }
    ChatReply:
      type: object
      required: [reply, remainingToday, resetsAt]
      properties:
        reply: { type: string }
        remainingToday: { type: integer }
        resetsAt: { type: string, format: date-time }
    NextStep:
      type: object
      required: [step]
      properties:
        step: { type: string, enum: [consent, questionnaire, photos, payment, confirming_payment, start_analysis, progress, home] }
```

---

## 4. C2 — Stripe webhook (external consumer: Stripe)

```yaml
openapi: 3.1.0
info: { title: Stripe webhook receiver, version: 1.0.0 }
paths:
  /payments/stripe/webhook:
    post:
      security: []
      summary: Receives Stripe events; the only way a payment's status changes (FR-015)
      parameters:
        - { name: Stripe-Signature, in: header, required: true, schema: { type: string } }
      requestBody:
        required: true
        content: { application/json: { schema: { type: object, description: "Raw Stripe Event; signature verified against the RAW body before parsing" } } }
      responses:
        "200": { description: "Processed, or already processed (idempotent by event id)" }
        "400": { description: "Signature invalid or payload unreadable; nothing changes" }
x-behaviour:
  handledEvents:
    - checkout.session.completed      # payment_status = paid → Payment.status = succeeded
    - checkout.session.async_payment_succeeded
    - checkout.session.async_payment_failed
    - checkout.session.expired        # Payment.status = failed (user may retry checkout)
  idempotency: "ProcessedWebhookEvent keyed by Stripe event id; unique constraint; concurrent duplicates → one record (AC6.3.2)"
  neverDoes: "Never starts analysis (FR-015); never trusts the redirect to the success URL"
  retries: "Return 200 only after the database commit; Stripe retries non-2xx"
```

---

## 5. In-process contracts between backend modules (shared schema)

These are the public Python interfaces each module exposes to other modules (units Q4). They are written as typed protocols. Types in `CamelCase` are data transfer objects; no ORM model crosses a module boundary.

```yaml
# shared-schema: backend module interfaces (Python Protocols)
C3_Identity:                       # provider U1/U2 — consumers: every backend module
  get_current_user: "FastAPI dependency (request) -> AuthenticatedUser{user_id, role} | raises NOT_AUTHENTICATED"
  get_account: "(user_id) -> AccountInfo{full_name, email, is_verified, member_since}"
  rule: "Background jobs never call get_current_user; they receive a verified user_id from the run record (see C7)"

C4_PhotoIntake:                    # provider U4 — consumers: U5, U6, U10
  check_identity: "(user_id) -> IdentityResult{status: incomplete|consistent|mismatch, mismatched_angles: list[str]} — fresh every call, nothing cached"
  snapshot_for_run: "(user_id) -> PhotoSnapshot{angle -> file_id} — only when consistent; raises PHOTO_IDENTITY_MISMATCH"
  set_state: "(user_id) -> PhotoSetState{complete: bool, consistent: bool}   # for Journey"

C5_Payments:                       # provider U5 — consumers: U6, U8, U10
  entitlement: "(user_id) -> Entitlement{paid: bool, payment_id: UUID | None}"
  payment_state: "(user_id) -> 'none' | 'pending' | 'paid'   # for Journey"

C6_Onboarding:                     # provider U3 — consumers: U6, U9, U10
  answers_for_ai: "(user_id) -> list[AnsweredQuestion{question_text, answer_text}] — NEVER includes a medical-flagged question or its follow-up (ADR-007)"
  distress_signals: "(user_id) -> DistressSignals{distress_level, appearance_frequency} — values only, for the tone rule"
  onboarding_state: "(user_id) -> OnboardingState{consented: bool, submitted: bool}   # for Journey"

C7_AnalysisPipeline_step_hook:     # defined by U6 — providers: FaceMeasurement, ReportWriting (U6), ImageGeneration (U7), Report (U8)
  register_step: "(name, order, handler: StepHandler) at application start"
  StepHandler: "(ctx: RunContext) -> StepResult{status: done|failed, reason}"
  RunContext: "{run_id, user_id (verified at start), photo_snapshot: angle -> file_id, answers_for_ai, distress_signals}"
  rules:
    - "The run captures photo_snapshot at start (C4.snapshot_for_run); every step, resume and later image retry uses those file ids — never 'current' photos (resolves domain review R-02)"
    - "A handler must be idempotent: re-running a completed step makes no second paid call"
    - "Steps run inside the worker process; 'async' in components.md means 'executed by the background worker'"
  order: "measuring(FaceMeasurement) → writing(ReportWriting) → generating_images(ImageGeneration) → assembling(Report)"

C8_MediaStore:                     # provider U4 — consumers: U4, U6, U7, U8
  put: "(owner_user_id, kind, bytes, content_type) -> StoredFileRef{file_id} — re-encodes photos, strips metadata, converts HEIC"
  get: "(file_id, requester_user_id | SYSTEM_WITH_RUN(run_id)) -> bytes | raises NOT_FOUND"
  retire: "(file_id) — replaced photos are retired, not deleted, while any run snapshot references them; deleted when unreferenced"

C9_Report:                         # provider U8 — consumers: U9, U10
  grounding_for_chat: "(user_id) -> ChatGrounding{assessments, feature_metrics, narratives_summary} | raises REPORT_NOT_READY"
  report_exists: "(user_id) -> bool   # for Journey"
  assemble_and_publish: "StepHandler for the 'assembling' step (C7)"

C10_vendor_ports:                  # provider = owning module; implementations selected by configuration (ADR-005)
  EmailSender: "send(to, template, variables) -> None | raises UPSTREAM_*   # Identity (U1)"
  PaymentGateway: "create_checkout(user_id, amount, currency, success_url, cancel_url) -> CheckoutSession; verify_webhook(raw_body, signature) -> Event   # Payments (U5) — the Stripe port the stories lacked"
  TextModel: "generate_structured(messages, images, json_schema) -> dict; chat(messages) -> str   # ReportWriting, BeautyAssistant (U6)"
  ImageEditor: "edit(source_image, instruction, fidelity) -> bytes   # ImageGeneration (U6 adapter, U7 use)"
  FileStorage: "write/read/delete(key)   # MediaStore (U4)"
  rules: "Every port call has a timeout; vendor errors become UPSTREAM_UNAVAILABLE/UPSTREAM_TIMEOUT; nothing personal is logged; each port has a test fake"
```

---

## 6. Behaviour at the boundaries (errors, timeouts, retries)

| Boundary | Timeout | Retries | On failure |
|---|---|---|---|
| Browser → API (C1) | Frontend request timeout 30 s (PDF and chat 60 s) | Only the single 401 → refresh → retry (FE-005); GET polls just repeat on their interval | Error toast from `message`; auth cleared only on `SESSION_INVALID` |
| Status polling (C1) | — | Every 2–3 s while the screen is visible; paused in background tabs | Keeps the last known state and shows "reconnecting" after 3 failures |
| Stripe → webhook (C2) | Stripe's own | Stripe retries non-2xx | 200 only after commit |
| Email port | 10 s | 2 retries with back-off | `UPSTREAM_UNAVAILABLE`; the code record stays usable for resend |
| Text model port | 60 s per call | Schema-invalid output retried up to a configured count (initially 2) | Step fails with reason (US7.9) |
| Image port | 120 s per image | 3 automatic retries, back-off on 429, configurable concurrency | Slot `failed`; up to 3 manual retries |
| Stripe API (checkout) | 10 s | 1 retry | `UPSTREAM_UNAVAILABLE`, nothing charged |
| In-process calls (C3–C9) | — | None (same process) | Typed domain errors mapped to C11 codes at the HTTP edge |

## 7. Contract ownership rules

1. **Ownership.**
   - The unit that builds a module owns its path group in C1 and its in-process interface (C3–C9).
   - U1 owns the overall OpenAPI document, the error format and the code list (C11).
   - U6 owns the step hook (C7).
   - U5 owns the Stripe webhook (C2).
2. **Source of truth.** FastAPI generates the OpenAPI document from code. The frontend's TypeScript client and types are generated from it, and CI fails if the committed types are out of date (Q6). This summary is the design intent; the generated document must match it.
3. **Additive changes** (a new endpoint, a new optional field, a new error code) are free. Consumers ignore unknown fields, and the frontend treats an unknown error code as `INTERNAL_ERROR`.
4. **Breaking changes** (removing or renaming a field or path, changing a type, changing a status code) update the backend, the generated types and the frontend in the same pull request, and are called out in the PR description with the requirement IDs affected.
5. **Client-fixed contracts:** `/auth/refresh`, `/auth/logout`, `/auth/me` and `/auth/change-password`, the cookie-only refresh token, and the 402 and 409 semantics are client-stated. They are not changed without a client scope change.
6. **Privacy rules are part of the contract:**
   - The medical flag is never sent to the browser.
   - `answers_for_ai` never returns medical answers.
   - Media is served only through owner-checked `/media/{fileId}`.
   - Another user's resource always returns 404.

## 8. Resolved from earlier reviews

| Earlier finding | Resolution here |
|---|---|
| Stories R-01: no story owns the Stripe adapter | `PaymentGateway` port (C10), owned and built by U5 with its fake |
| Domain R-02: a run can read changed or deleted photos | `snapshot_for_run` + `RunContext.photo_snapshot` + MediaStore `retire` (C4, C7, C8) |
| Domain R-04: background paths vs auth checks | Background steps take a verified `user_id` from the run, never the HTTP auth dependency (C3, C7) |
| Domain R-06: meaning of async | Defined in C7 |
| Units R-03: U6 → U7 direction | U7 registers into U6's step hook (C7) |

## 9. Open questions

| Contract | Question | Blocks |
|---|---|---|
| C1 `/report/pdf` | Domain review R-01: the PDF must be rendered from a server-side template Report owns, not the frontend page. Template approach (HTML + headless Chromium in the backend, or WeasyPrint) to be chosen in NFR/Infrastructure Design | U8 |
| C1 `QuestionnaireDefinition` | Q9/Q11 follow-up shape and the Q19 branching condition are open with the client ([QS] §5); the schema supports both shapes | U3 |
| C1 `Dashboard` | Items marked TBD in [RD] (protocol phases count, facial age, priority-feature rule, Feature Evaluation zones) stay nullable until decided | U8 |
| C1 photo checks | `PHOTO_REJECTED` reason list is final only when thresholds are set (`ASM-002`) | U4 |
| C11 `UPSTREAM_*` | Whether a 502 on sign-up email send should keep the unverified account or roll back (currently keeps it; resend works) | U1 |
| C10 `ImageEditor` | Exact vendor parameters for "high input fidelity" depend on the vendor's current API; the port hides them | U7 |
| Cookie attributes | `SameSite` value depends on whether frontend and backend end up on the same site once hosting is chosen (`None; Secure` for cross-site, `Lax` for same-site) | U1 (configurable now) |
