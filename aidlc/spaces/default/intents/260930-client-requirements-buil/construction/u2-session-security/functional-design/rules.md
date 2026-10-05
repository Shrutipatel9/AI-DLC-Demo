# Business Rules — U2 Session Security

Rules for resend and lockout, session restore and refresh, reuse detection, CSRF, logout, password reset and change, multi-tab coordination and app-wide feedback. Rule numbers restart for this unit (`BR{group}.{seq}`); U1 rules are cited as "U1 BRx.y".

Sources:
- requirement IDs from `requirements.md` (FR2.x, FR3.x, FR13.2, FR14.x);
- client IDs (`AUTH-*`, `FE-*`);
- ADR-006;
- this unit's answers in `functional-design-questions.md` (Q1–Q3).

```yaml
rules:
  # BR1 — Resend and lockout
  - id: BR1.1
    statement: A new code for the same account and purpose can be requested 60 seconds after the previous send; the screen counts down and enables the resend control by itself.
    category: policy
    applies_to: VerificationAttemptCounter.lastSentAt
    trigger: POST /auth/resend-code
    logic: IF now < lastSentAt + 60 s THEN refuse with the seconds left ELSE send a new code
    violation: 429 CODE_RESEND_COOLDOWN with Retry-After
    source: FR2.4, AUTH-011, AC3.3.1
  - id: BR1.2
    statement: A resent code replaces the previous one; the previous code no longer verifies.
    category: policy
    applies_to: OneTimeCode.supersededAt
    trigger: successful resend
    logic: mark the live code for (user, purpose) superseded, then issue a new one
    violation: an old code returns 401 CODE_INVALID
    source: AC3.3.2, U1 BR2.6
  - id: BR1.3
    statement: After the 5th wrong code for an account and purpose, every code (even a correct one) and every resend for that purpose is refused for 15 minutes; resending never resets the count.
    category: policy
    applies_to: VerificationAttemptCounter
    trigger: POST /auth/verify, /auth/password/verify-code, /auth/resend-code, /auth/login
    logic: IF now < lockedUntil THEN refuse with the seconds left
    violation: 429 CODE_LOCKED with Retry-After
    source: FR2.4, AUTH-011, AC3.3.3
  - id: BR1.4
    statement: When the lockout ends, the count starts again from zero; a new correct code then succeeds and resets the count.
    category: policy
    applies_to: VerificationAttemptCounter
    trigger: first verify or resend at or after lockedUntil
    logic: IF lockedUntil <= now THEN failedCount := 0, lockedUntil := empty, before evaluating
    violation: n/a
    source: AC3.3.4
  - id: BR1.5
    statement: The resend response is the same whether or not a matching account exists; an email is sent only to a real account in the right state for the purpose.
    category: policy
    applies_to: POST /auth/resend-code
    trigger: resend for an unknown email, or a purpose that does not match the account state
    logic: IF no matching account in the right state THEN respond 202 with the same CodeSent shape and send nothing
    violation: n/a
    source: FD Q1 [Decided by delivery team], BR-009 anti-enumeration spirit
  - id: BR1.6
    statement: The right state per purpose is signup → an unverified account; login → a verified account (a resend must not bypass the password check, so a login resend is honoured only within 10 minutes of a successful password step); password_reset → a verified account with a reset request in the last 10 minutes.
    category: constraint
    applies_to: POST /auth/resend-code
    trigger: resend
    logic: check the purpose-specific state before sending
    violation: silent no-send under BR1.5
    source: FR2.4, FR2.12 [Decided by delivery team for the 10-minute bound]

  # BR2 — Session restore, refresh, reuse detection, CSRF
  - id: BR2.1
    statement: A usable refresh cookie is exchanged for a new access token and a new refresh cookie; the old session is marked rotated and the new one joins the same family.
    category: policy
    applies_to: RefreshSession
    trigger: POST /auth/refresh
    logic: IF the session is usable THEN rotatedAt := now on it; create a child (same familyId, parentTokenId) with a fresh 7-day expiry; return the access token and Set-Cookie
    violation: n/a
    source: FR2.5, FR2.7, AUTH-010, AUTH-012, AC3.5.3
  - id: BR2.2
    statement: A refresh session is valid for 7 days from its own issue; a refresh at or after expiry is refused.
    category: validation
    applies_to: RefreshSession.expiresAt
    trigger: POST /auth/refresh
    logic: IF now >= expiresAt THEN refuse
    violation: 401 SESSION_INVALID (reason EXPIRED), cookie cleared
    source: FR2.5, AC3.5.2
  - id: BR2.3
    statement: Presenting a refresh session that was already rotated revokes every session in its family; the user must sign in again.
    category: authorization
    applies_to: RefreshSession.familyId
    trigger: POST /auth/refresh with a rotated session
    logic: IF rotatedAt is set THEN revokedAt := now, revokedReason := reuse_detected on every session in the family
    violation: 401 SESSION_INVALID (reason REUSE_DETECTED), cookie cleared
    source: FR2.6, AUTH-012, AC3.6.1, ADR-006 (no grace window)
  - id: BR2.4
    statement: A missing, malformed, unknown, revoked or wrong-secret refresh cookie is refused without revealing which.
    category: validation
    applies_to: POST /auth/refresh
    trigger: any refresh that is not BR2.2 or BR2.3
    logic: refuse; compare the secret hash in constant time
    violation: 401 SESSION_INVALID (reason INVALID), cookie cleared
    source: FR2.7, NFR2
  - id: BR2.5
    statement: The cookie-authenticated endpoints (refresh, logout) require the X-Requested-With header and an Origin (or, if absent, Referer) on the allow-list; a refused request changes no session.
    category: authorization
    applies_to: POST /auth/refresh, POST /auth/logout
    trigger: every call
    logic: IF X-Requested-With is missing or wrong OR Origin/Referer not allowed THEN refuse before reading the cookie
    violation: 403 CSRF_CHECK_FAILED
    source: FR2.11, AUTH-013, AC3.6.2
  - id: BR2.6
    statement: Access tokens stay valid for exactly 15 minutes; a protected endpoint accepts a token at T+14:59 and refuses it at T+15:00.
    category: validation
    applies_to: access token
    trigger: any protected request
    logic: reuse U1 BR4.1 and BR4.3
    violation: 401 NOT_AUTHENTICATED
    source: AUTH-002, AC3.6.3
  - id: BR2.7
    statement: The server stores only the refresh token identifier and a hash of its secret; no raw refresh token is ever stored or logged.
    category: constraint
    applies_to: RefreshSession
    trigger: every session write
    logic: reuse U1 BR4.2
    violation: n/a (test)
    source: AUTH-010, AC3.5.3
  - id: BR2.8
    statement: The refresh cookie is HttpOnly with Max-Age equal to the configured 7 days; Secure, SameSite and Path come from configuration; every response that ends a session clears it with Max-Age=0.
    category: constraint
    applies_to: refresh cookie
    trigger: verify, refresh, logout, refused refresh
    logic: set or clear the cookie with the configured attributes
    violation: n/a
    source: FE-002, AC3.5.4

  # BR3 — Logout
  - id: BR3.1
    statement: Logout revokes the current refresh session, clears the cookie and succeeds even if the cookie is already missing or invalid.
    category: policy
    applies_to: RefreshSession
    trigger: POST /auth/logout (after BR2.5)
    logic: IF the cookie names a usable session THEN revokedAt := now, revokedReason := logout; always clear the cookie and respond 204
    violation: n/a
    source: FR2.8, AUTH-006, AC3.7.2, AC3.7.3
  - id: BR3.2
    statement: Logout asks for confirmation in the shared dialog; cancelling keeps the user signed in.
    category: policy
    applies_to: WebApp
    trigger: user chooses Log out
    logic: open the confirmation dialog; only "Log out" in the dialog calls the store's logout
    violation: n/a
    source: FR14.2, BR-010, AC3.7.1
  - id: BR3.3
    statement: Page unload, visibility change, tab close or route change never logs out or clears the store.
    category: constraint
    applies_to: WebAuthClient
    trigger: browser lifecycle events
    logic: no handler on these events touches the session
    violation: n/a (test)
    source: FE-006, FR3.5, AC3.7.4
  - id: BR3.4
    statement: A logout in one tab signs out every open tab of the app in that browser at once.
    category: policy
    applies_to: WebAuthClient
    trigger: successful logout in any tab
    logic: broadcast "signed out (logout)" to other tabs; each clears its store and goes to login
    violation: n/a
    source: FD Q3 [Decided by delivery team], FR3.5 (explicit logout)

  # BR4 — Forgotten password
  - id: BR4.1
    statement: The reset request always gives the same response and shows no toast with the outcome; a code is emailed only if a verified account has that email.
    category: policy
    applies_to: POST /auth/password/forgot
    trigger: reset request
    logic: IF a verified account exists AND it is not in cooldown or lockout THEN issue a password_reset code; ALWAYS respond 202 with the same body
    violation: n/a
    source: FR2.12, AUTH-015, BR-009 exception, AC3.9.1, AC11.7.1
  - id: BR4.2
    statement: Reset codes follow the same rules as other codes (6 digits, 10-minute validity, single use, 60 s cooldown, 5 failures → 15-minute lockout) under their own purpose password_reset.
    category: validation
    applies_to: OneTimeCode, VerificationAttemptCounter
    trigger: POST /auth/password/verify-code
    logic: reuse U1 BR2.1–BR2.7 with purpose password_reset
    violation: 401 CODE_INVALID / CODE_EXPIRED, 429 CODE_LOCKED
    source: FR2.12, AC3.9.2
  - id: BR4.3
    statement: A verified reset code yields one opaque reset token valid for the configured window (initially 10 minutes); only its hash is stored, and issuing a new one makes earlier unused ones unusable.
    category: policy
    applies_to: PasswordResetToken
    trigger: successful reset-code verification
    logic: create the token; mark earlier unused tokens of the user as used; return the raw token once
    violation: n/a
    source: FR2.12, AUTH-015, AC3.9.2, AC3.9.3
  - id: BR4.4
    statement: A reset token is refused if used before, expired (at exactly the window end), unknown, or presented as a Bearer access token.
    category: validation
    applies_to: PasswordResetToken
    trigger: POST /auth/password/reset, any protected request carrying it
    logic: IF usedAt set OR now >= expiresAt OR no match THEN refuse; a reset token never parses as an access token
    violation: 401 RESET_TOKEN_INVALID (reset) / 401 NOT_AUTHENTICATED (as Bearer)
    source: FR2.12, AC3.9.2, AC3.9.3
  - id: BR4.5
    statement: The new password must meet the sign-up password rule.
    category: validation
    applies_to: User.passwordHash input
    trigger: password reset, password change
    logic: reuse U1 BR1.2
    violation: 422 VALIDATION_FAILED (PASSWORD_TOO_WEAK)
    source: AC3.9.5, AC11.5.1
  - id: BR4.6
    statement: A successful reset sets the new password hash, marks the reset token used and revokes every refresh session of the account on every device, in one transaction.
    category: policy
    applies_to: User, PasswordResetToken, RefreshSession
    trigger: POST /auth/password/reset success
    logic: update passwordHash; usedAt := now; revokedAt := now, revokedReason := password_reset on all the user's usable sessions
    violation: n/a
    source: FR2.12, AC3.9.4

  # BR5 — Change password (signed in)
  - id: BR5.1
    statement: Changing the password requires the correct current password; a wrong one is refused and changes nothing.
    category: authorization
    applies_to: POST /auth/change-password
    trigger: change request
    logic: IF the current password does not verify THEN refuse
    violation: 401 INVALID_CREDENTIALS (contract C1); the form shows it on the currentPassword field, and BR6.4 keeps it from triggering a refresh
    source: FR2.13, AUTH-016, AC11.5.3
  - id: BR5.2
    statement: The new and confirm fields must match before any request is sent; the confirm field exists only in the form.
    category: validation
    applies_to: change-password form
    trigger: submit
    logic: IF new != confirm THEN show an inline error on confirm and send nothing
    violation: inline field error
    source: FR13.2, AC11.5.2
  - id: BR5.3
    statement: After a change the current session stays signed in, and every other refresh session of the account is revoked.
    category: policy
    applies_to: RefreshSession
    trigger: successful change
    logic: keep the session named by the request's refresh cookie; revokedAt := now, revokedReason := password_changed on all other usable sessions
    violation: n/a
    source: AUTH-016, AC11.5.1, FD Q2 [Decided by delivery team for other devices]

  # BR6 — Frontend session (WebAuthClient)
  - id: BR6.1
    statement: On app start each tab restores the session by calling refresh; protected screens show a loading indicator until it finishes and never flash the login screen.
    category: policy
    applies_to: ClientSession.status
    trigger: app start or reload
    logic: status := initializing; refresh → signedIn on success, signedOut on 401; on network/5xx stay initializing with a retry message
    violation: n/a
    source: FR3.3, FE-002, AC3.5.1, AC3.5.2
  - id: BR6.2
    statement: The client refreshes the access token one minute before it expires.
    category: policy
    applies_to: WebAuthClient
    trigger: timer at accessTokenExpiresAt − 60 s
    logic: schedule one refresh; no refresh before then
    violation: n/a
    source: FR3.4, FE-005, AC3.10.1
  - id: BR6.3
    statement: A request that gets 401 NOT_AUTHENTICATED triggers one shared refresh and is retried once; any number of concurrent 401s and a proactive refresh in flight share one refresh call.
    category: policy
    applies_to: API client
    trigger: 401 with code NOT_AUTHENTICATED
    logic: join the in-flight refresh or start it; on success retry each waiting request once
    violation: n/a
    source: FR3.4, FE-005, AC3.10.2
  - id: BR6.4
    statement: A retried request that gets 401 again is not retried; a 401 from refresh itself never starts another refresh; only NOT_AUTHENTICATED (never INVALID_CREDENTIALS, CODE_* or other 401 codes) counts as an expired session.
    category: constraint
    applies_to: API client
    trigger: 401 responses
    logic: retry budget of one per request; refresh calls bypass the 401 handler; branch on code
    violation: n/a
    source: FE-005, AC3.10.3
  - id: BR6.5
    statement: The store is cleared and the app sent to login only when refresh returns 401 or the user logs out — exactly once even with many waiting requests; network errors and 5xx keep the user signed in with an error toast.
    category: constraint
    applies_to: ClientSession
    trigger: refresh outcome
    logic: 401 → clear once, reject waiters, navigate once; network/5xx → reject waiters, error toast, stay signedIn
    violation: n/a
    source: FR3.5, FE-006, AC3.10.4, AC3.10.5
  - id: BR6.6
    statement: Tabs coordinate refresh so that only one tab refreshes at a time and the others reuse its result; the server keeps strict reuse detection.
    category: policy
    applies_to: WebAuthClient
    trigger: any refresh (start-up, proactive, 401)
    logic: take a browser-wide lock; after acquiring, if another tab refreshed within the last few seconds use its broadcast result, else refresh and broadcast the new access token and expiry; fall back to per-tab refresh when locks and broadcast are unavailable
    violation: n/a
    source: ADR-006, FR2.6, FR3.5, AC3.11.1
  - id: BR6.7
    statement: After a session is ended for security (reuse detected, password reset or change elsewhere), the login screen says in plain language that the user was signed out for security.
    category: policy
    applies_to: login screen
    trigger: refresh 401 with reason REUSE_DETECTED or REVOKED
    logic: signedOutReason := security; login shows the message once
    violation: n/a
    source: AC3.6.4 [Recommendation in stories]
  - id: BR6.8
    statement: No token, user profile or auth flag is ever written to Web Storage or a persisted store.
    category: constraint
    applies_to: WebAuthClient
    trigger: always
    logic: reuse U1 BR5.1
    violation: n/a (lint + test)
    source: FE-002, AC3.5.5

  # BR7 — App-wide feedback
  - id: BR7.1
    statement: Every user action with a real success or failure outcome shows a toast at the top right, except the forgot-password request.
    category: policy
    applies_to: WebApp
    trigger: action outcome
    logic: success/error toast through the shared toast service
    violation: n/a
    source: FR14.1, BR-009, AC11.7.1
  - id: BR7.2
    statement: Toasts are announced by screen readers without taking focus; error toasts stay until dismissed; success toasts disappear after 5 seconds.
    category: constraint
    applies_to: toast
    trigger: toast shown
    logic: polite live region for success, assertive for errors; no focus move
    violation: n/a
    source: FR14.1, NFR9, AC11.7.2
  - id: BR7.3
    statement: Every destructive or irreversible action opens the shared confirmation dialog first; focus moves into it and is trapped, Escape cancels, focus returns to the opener, and the confirm button names the action.
    category: constraint
    applies_to: confirmation dialog
    trigger: destructive action
    logic: dialog with title, body, cancel and a named confirm button
    violation: n/a
    source: FR14.2, BR-010, AC11.7.3
  - id: BR7.4
    statement: Invalid form input shows text next to the field, linked to it for assistive technology; a toast may add to it but never replaces it.
    category: constraint
    applies_to: forms
    trigger: validation failure (client or server field details)
    logic: field error with aria-describedby and aria-invalid
    violation: n/a
    source: FR14.1, NFR9, AC11.7.4
  - id: BR7.5
    statement: On a phone-width screen, toasts appear below the header and never cover the header navigation or the control they report on.
    category: constraint
    applies_to: toast
    trigger: viewport under 640 px
    logic: toast region offset below the header; stacked, max 3 visible
    violation: n/a
    source: AC11.7.5
```

## Rules summary

| Group | Rules | Topic |
|---|---|---|
| BR1 Resend and lockout | BR1.1–BR1.6 | 60 s cooldown, supersede, 5/15 lockout with resend refused, reset after lockout, same answer for unknown emails, state per purpose |
| BR2 Sessions | BR2.1–BR2.8 | Rotation, 7-day validity, strict reuse detection, generic refusal, CSRF on cookie endpoints, 15-minute access token, hashed storage, cookie attributes |
| BR3 Logout | BR3.1–BR3.4 | Revoke and clear, confirmation, no logout on lifecycle events, all tabs sign out |
| BR4 Reset | BR4.1–BR4.6 | Same response, code rules, opaque hashed single-use token, refusals, password rule, revoke all sessions |
| BR5 Change | BR5.1–BR5.3 | Current password required, confirm matches in the form, keep this session and revoke others |
| BR6 Frontend session | BR6.1–BR6.8 | Restore on start, proactive refresh, single-flight retry, retry limits, clear only on 401/logout, cross-tab lock, security message, no Web Storage |
| BR7 Feedback | BR7.1–BR7.5 | Toasts, accessibility, confirmation dialog, inline errors, phone layout |
