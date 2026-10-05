# Post-Review Changes — Functional Design, U2 Session Security

The files in this folder are kept exactly as the architecture reviewer saw them (review iteration 1, verdict NOT-READY; `reviews/review-01.md`). This note **amends** them. Where it conflicts with `rules.md`, `functional-spec.md`, `entities.md` or `frontend-components.md`, this note wins, and later stages (NFR, infrastructure, code generation) build to it. The approach was chosen by the human for U1 on 2026-10-01 and is applied the same way here. The decisions below are **[Decided by delivery team]** unless noted.

## Major findings

### R-01 — Anti-enumeration must survive throttling
- **Non-revealing endpoints:**
  - `/auth/password/forgot`, and `/auth/resend-code` for the purposes `login` and `password_reset`, always answer 202 with the `CodeSent` shape. This holds during cooldown and lockout too: those cases send nothing, and the screen keeps its own 60 s countdown.
  - `CODE_RESEND_COOLDOWN` and `CODE_LOCKED` stay visible only on the `signup` purpose, where FR2.1 already reveals registration.
  - BR1.1 and BR1.3 are narrowed accordingly for these endpoints.
- **Verify for an unknown email:**
  - For `/auth/verify` (purpose `login`) and `/auth/password/verify-code`, an unknown email uses a **shadow counter** keyed by a keyed hash of the normalised email (new entity `EmailAttemptCounter`: `emailHash`, `purpose`, `failedCount`, `lockedUntil`).
  - After 5 tries it returns `CODE_LOCKED` exactly as a real account would, so real and fake accounts behave the same.
- **Equal response work:** on the non-revealing endpoints, the email is sent after the response (a background task), never before it. A send failure is logged at ERROR and the user can resend. The response always takes the same work: one HMAC, one counter upsert and the same reply shape.

### R-02 — Logout must win over a racing refresh
- **Server:**
  - `/auth/logout` resolves the cookie's `tokenId`, including a session that was already rotated, to its `familyId`.
  - It then revokes **every** session in that family (`revokedReason = logout`) and clears the cookie.
  - BR3.1 now reads "revoke the family named by the cookie".
- **Client:**
  - `logout()` first takes the `auth-refresh` lock and bumps a store **generation counter**.
  - Any refresh result tagged with an older generation is discarded, and a late refresh result never moves the store from `signedOut` back to `signedIn`.
  - The logout call is made while the lock is held.
- **Tests:** logout during an in-flight refresh in another tab, and logout with a rotated cookie.

### R-03 — Change password and the current session
- **Cookie path:** the refresh cookie `Path` must be `/auth`, which covers `/auth/refresh`, `/auth/logout` and `/auth/change-password`. The settings validator refuses any other value. This narrows BR2.8's "Path from configuration".
- **Identifying the current session:**
  - The cookie session must belong to the Bearer user (`userId` match); otherwise it is ignored.
  - The current session is resolved through its family: the family's newest usable session is kept.
  - Every other usable session of the user, in any family, is revoked with reason `password_changed`.
- **No valid cookie:**
  - The password still changes, all sessions are revoked, and the response is 204.
  - After any successful change, the client immediately runs a coordinated refresh.
  - If that refresh returns 401, the store signs out with reason `security`, and login shows "Your password was changed. Please log in again."
  - So the user is never dropped silently.
- **Contract note:** Q2 extends C1 for other devices only. C1's "the current session stays valid" is kept exactly. This is recorded as a delivered clarification.

### R-04 — A lost refresh response must not look like token theft
- **Idempotent retry:** each refresh call sends a random per-call `X-Refresh-Attempt` id (128 bits, held in the calling tab's memory only, reused on retries of the same refresh). The server stores it on the child session it creates.
- **Recovery:** if a rotated session is presented again **with the same attempt id**, the child is still unused, and the child was created at most 60 seconds ago, then the server re-issues that child instead of treating it as reuse. It mints a new secret, updates the hash and returns 200.
- **Everything else stays strict:** any other replay of a rotated session still revokes the family (BR2.3).
- **Why this is safe:** a stolen cookie carries no attempt id, because the id never leaves the legitimate tab's memory. ADR-006's strictness against theft is therefore unchanged. This is an addendum to ADR-006.
- **Client:** a refresh that fails with a network error or 5xx is retried once with the **same** attempt id before BR6.5's "stay signed in" path. A `REUSE_DETECTED` outcome is logged at WARN with the family id.
- **Tests:** refresh response lost, then retry with the same id → signed in; replay with a different id or no id → family revoked.

## Minor findings
| Finding | Resolution |
|---|---|
| R-05 | `/auth/refresh` returns `AccessToken` only (C1 unchanged). Restore (WF-U2-2) and the cross-tab broadcast run refresh and then `GET /auth/me`, and the loader stays up until both finish. If `/auth/me` fails with a network error or 5xx after a successful refresh, the app stays `initializing` with the Retry message. A 401 there follows the normal single-flight path. The broadcast carries the `user` that the refreshing tab fetched |
| R-06 | `VerificationAttemptCounter` gains `flowStartedAt`, set when a sign-up, a successful login password step or a reset request starts a flow, and never moved by a resend. BR1.6's 10-minute windows are measured from it. `EmailAttemptCounter` (R-01) has the same field |
| R-07 | Each refresh fetch has a 10 s timeout, so the lock is always released. The 5 s adoption window is measured from the moment the waiting tab **received** the broadcast. A tab whose refresh returns 401 broadcasts `{type: "signedOut", reason}`. Reason mapping: `INVALID` and `EXPIRED` → `session_expired` ("Your session ended. Please log in again."); `REUSE_DETECTED` and `REVOKED` → `security` (BR6.7 message); logout → `logout` (no notice) |
| R-08 | BR2.5: when neither `Origin` nor `Referer` gives an allow-listed origin, including `Origin: null`, the request is refused with 403 `CSRF_CHECK_FAILED`. Tested |
| R-09 | A reset token is 32 bytes (256 bits) from a CSPRNG, base64url-encoded, and only its SHA-256 is stored. Single use is an atomic conditional update (`usedAt` empty and `now < expiresAt`) with a row-count check, so two concurrent resets with one token give exactly one success. **Accepted residual risk:** access tokens already issued on other devices stay valid for up to 15 minutes after a reset or password change (AUTH-002 lifetime), because their refresh is refused and they then sign out |
| R-10 | The per-IP limiter answers 429 `RATE_LIMITED` with `Retry-After`, a valid `ErrorResponse`. This is the contract extension added in U1 (U1 plan D3, already in the OpenAPI document). It applies to `/auth/resend-code`, `/auth/password/forgot`, `/auth/password/verify-code`, `/auth/password/reset` and `/auth/change-password`. On the non-revealing endpoints it applies per IP only, never per account, so it reveals nothing about accounts |

## Traceability impact
No AC changes owner. The amendments refine BR1.1, BR1.3, BR1.6, BR2.3, BR2.5, BR2.8, BR3.1, BR4.3, BR4.4, BR5.3, BR6.1, BR6.5, BR6.6 and BR6.7. They add the entity `EmailAttemptCounter` and the field `flowStartedAt`.
