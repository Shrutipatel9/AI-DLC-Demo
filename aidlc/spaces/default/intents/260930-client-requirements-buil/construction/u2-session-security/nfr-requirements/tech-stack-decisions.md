# Tech Stack Decisions — U2 Session Security

U2 adds no new runtime dependency. Everything builds on U1's stack (`u1-walking-skeleton/nfr-requirements/tech-stack-decisions.md`).

## Choices for this unit

| Area | Choice | Rationale |
|---|---|---|
| Cross-tab lock | Browser **Web Locks API** (`navigator.locks.request("auth-refresh", ...)`) | ADR-006. Supported by the latest two versions of Chrome, Edge, Firefox and Safari (NFR9). No library needed. |
| Cross-tab messages | **BroadcastChannel** `"auth"` | Same-origin only, so other sites can't read it. No library needed. |
| Background email send | FastAPI `BackgroundTasks` running the U1 email dispatcher (with its bulkhead and 25 s budget) after the response | Equal response work for the non-revealing endpoints (R-01). No queue infrastructure; the U6 worker is not needed here. |
| Email hash for shadow counters | HMAC-SHA-256 with `EMAIL_HASH_KEY` over the normalised email | Stable, non-reversible key for unknown emails. |
| Reset and attempt ids | Python `secrets.token_urlsafe(32)` and `secrets.token_bytes(16)`; browser `crypto.getRandomValues` | CSPRNG on both sides. |
| UI primitives | shadcn/ui `AlertDialog` (confirmation) and the existing Sonner toasts (U1), wrapped as a toast service | Already in the project; accessible. |
| Fake timers in tests | Vitest `vi.useFakeTimers()`; backend `FrozenClock` (U1) | Team practice: an injectable clock for every timing test. |

## Engineering-quality requirements for this unit

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR7.1 | Layering holds: UI components use only `useAuth()` selectors and store actions; refresh coordination stays private to `lib/auth`. Backend session logic sits in Identity services, and routes stay thin. | ESLint `no-restricted-imports` and import-linter contracts (extended for the new modules) |
| NFR8.1 | **Test-first:** the backend refresh and reuse-detection logic (JWT and session service, `AUTH-010`–`AUTH-012`) and the reset-code flow (OTP service), plus the frontend single-flight refresh, retry rules and cross-tab coordination (`FE-005`, `FE-006`, ADR-006). Red output is recorded before implementation. | Code summary Red evidence |
| NFR8.2 | Line coverage stays at or above 80% for each app after U2. | CI coverage gates |
| NFR8.3 | **Playwright session journey:** reload stays signed in; two tabs refresh without being logged out; logout in one tab signs out the other; forgot → code from Mailpit → reset → login with the new password; change password keeps this tab signed in. Run at both viewports, with axe. | E2E job and the checkpoint command |
| NFR1.1 | **Migration `0002_u2_session_security`:** adds `password_reset_tokens`, `email_attempt_counters`, `flow_started_at` on the attempt counters, and the refresh-session columns (`revoked_reason`, `attempt_id`) with the NFR11.4 indexes. Downgrade is clean. | Alembic round-trip |
