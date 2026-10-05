# Post-Review Changes — NFR Design, U2 Session Security

The design files in this folder are kept exactly as the reviewer saw them (review iteration 1, verdict NOT-READY; `reviews/review-01.md`). This note **amends** them. Where they conflict, this note wins, and code generation builds to it. All entries are **[Decided by delivery team]**.

## Major findings

### R-01 — Revocations must catch a racing refresh
Every revocation (logout, reset, change) is **lock-then-update** in one transaction:
1. `SELECT token_id FROM refresh_sessions WHERE <scope> ORDER BY token_id FOR UPDATE`. The scope is the cookie's family for logout, or the user's sessions for reset and change. This waits for any in-flight refresh holding a lock in that scope.
2. Then a **separate** `UPDATE refresh_sessions SET revoked_at = now, revoked_reason = :r WHERE <scope> AND revoked_at IS NULL`. A new statement takes a new snapshot, so it sees the child committed by the refresh it waited for.

In addition, the refresh transaction re-reads the parent's `revoked_at` after inserting the child, while still holding the lock. If the parent was revoked, it marks the child revoked too and returns 401 `REVOKED`.

**Tests:** logout racing a refresh, reset racing a refresh, and change racing a refresh. Each must end with zero usable sessions in scope (zero, except the kept family for change).

### R-02 — Refresh exchange, final pseudocode

```text
BEGIN (one transaction; every branch commits its writes before the response; 401 responses clear the cookie)
  p = SELECT … WHERE token_id=:id FOR UPDATE           -- parent first
  verify secret (constant time) → else 401 INVALID
  p.revoked_at → 401 REVOKED;  now >= p.expires_at → 401 EXPIRED
  if p.rotated_at:
     c = SELECT child WHERE parent_token_id=p.token_id FOR UPDATE   -- child second (no deadlock: same order everywhere)
     if valid_attempt(header) and c.attempt_hash == sha256(header) (constant time)
        and c.rotated_at IS NULL and c.revoked_at IS NULL and now - c.issued_at <= 60 s:
          c.secret_hash = sha256(new_secret); COMMIT → 200 recovered (Set-Cookie c)
     lock-then-update family revoke (R-01) reason reuse_detected; COMMIT → 401 REUSE_DETECTED
  c = INSERT child(family, parent=p, attempt_hash = sha256(header) if valid_attempt(header) else NULL)
  p.rotated_at = now; re-check p.revoked_at (R-01); COMMIT → 200 (Set-Cookie c)
```

- `valid_attempt` means exactly 22 base64url characters. A child with a NULL `attempt_hash` is never recoverable.
- Error branches return a response object; they do not raise. The writes therefore commit before the 401, and the session-per-request dependency's rollback never undoes a family revoke.
- Every 401 response carries `Set-Cookie: refresh_token=; Max-Age=0; Path=/auth`.

### R-03 — Equal work on the non-revealing endpoints
- **Code issuance moves into the background task**, after the response, on every branch where a code would be sent: generate, hash, supersede, insert and send.
- Before the response, **every** branch (real, unknown, cooldown, locked) runs the same work: the email HMAC, a counter upsert and a fixed dummy HMAC for the code, then builds the identical 202 body.
- **Timing test:** `tests/identity/test_perf_enumeration.py` (`perf` marker) takes 200 samples per branch and asserts that the median and the p95 differ by less than 50 ms (NFR2.11 and requirements post-review R-06). It is part of `make verify` and the CI perf step.

### R-04 — Login password step during a login lockout
`/auth/login` order:
1. Rate limit.
2. Look up the user.
3. Run the password check, with the dummy hash for unknown users.
4. On a wrong password or an unknown user → 401 `INVALID_CREDENTIALS`.
5. Only after a correct password, check the login lockout → 429 `CODE_LOCKED` with `Retry-After` set to the seconds until `lockedUntil`.
6. Otherwise issue the login code.

Because the lock is tested only after a correct password, the lockout reveals nothing to someone who does not know the password, so it is not an enumeration oracle. **Tests:** real-locked + correct password → 429; real-locked + wrong password → 401; unknown → 401.

### R-05 — Accessibility of toasts and the dialog (NFR9.9)

| Clause | Component behaviour | Test |
|---|---|---|
| Focus moves into the dialog on open | `AlertDialog` focuses the **Cancel** button first. This is the safe default for destructive actions | RTL: `document.activeElement` is Cancel |
| Focus trapped | Tab and Shift+Tab cycle within the dialog | RTL keyboard test, both directions |
| Escape cancels | Escape resolves `confirm()` to false | RTL |
| Focus returns to the opener | The dialog stores the opener and restores it on close | RTL |
| Confirm names the action | The `confirmLabel` parameter is required; the type does not accept a generic "OK" | Type and unit test |
| Toast roles | Success uses `role="status"` with `aria-live="polite"`; error uses `role="alert"` | RTL |
| No focus steal | Showing a toast leaves `activeElement` unchanged | RTL |
| Keyboard dismissal | Each toast has a close button reachable by Tab | RTL |
| Timing | Success toasts auto-dismiss at 5 s; error toasts persist | Vitest fake timers |
| Automated scan | axe runs on the logout dialog and on a toast in the Playwright session journey | Playwright + axe |

NFR9.9 and NFR2.17 are added to traceability with the targets above and in R-06. The traceability file is not edited after the review; this note is the record.

## Minor findings

| Finding | Resolution |
|---|---|
| R-06 CORS details | `CORSMiddleware` is the **outermost** layer, so 403, 429 and 5xx responses carry CORS headers. `allow_methods = ["GET", "POST", "OPTIONS"]`. Origins are normalised to `scheme://host[:port]` (lower-case, no trailing slash, default ports dropped) for both CORS and CSRF. Order on cookie endpoints: CORS → CSRF → refresh rate limit → handler. Preflight tests from allowed and other origins cover `/auth/refresh`, `/auth/logout` and `/auth/change-password` |
| R-07 Logging | Drop `emailHashPrefix`. `auth.code.locked` logs `userId` for real accounts and **no identifier** for shadow counters. One allow-list addition: `familyId`, `reason`, `count`, `sent`, `outcome`, `purpose`. Add `auth.sessions.revoked` (count, reason), emitted by reset and change. `auth.session.refreshed` is DEBUG (no sampling machinery). NFR5.12's "INFO, debug-sampled" is read as "not at INFO" |
| R-08 Coordinator | (a) `logout()` takes the `auth-refresh` lock, increments the generation, calls `/auth/logout`, broadcasts `signedOut`, then releases. (b) A single retry runs **after** the lock is released and the lock is re-acquired, so no hold exceeds 10 s. (c) Idle tabs apply a `refreshed` broadcast immediately on receipt if its `expiresAt` is later than their current token's; otherwise they ignore it. (d) `GET /auth/me` runs only on restore and only in the tab that performed the network refresh, **after** the lock is released; adopting tabs take `user` from the broadcast. (e) Fallback claim: the claim with the smallest `(timestamp, randomId)` wins. A loser that sees no `refreshed` broadcast within 12 s performs its own refresh. |
| R-09 Change-password scope | Verify the cookie secret, in constant time, before trusting its family. Keep the **whole cookie family**, which has at most one usable session, and revoke every other family of the user (lock-then-update, R-01). A missing or invalid cookie revokes all families (the post-review case in the functional design) |
| R-10 Clean-up and migration | `parent_token_id` has `ON DELETE SET NULL`. Batches select `… ORDER BY token_id LIMIT 1000 FOR UPDATE SKIP LOCKED` and delete. A second run deletes nothing. Migration `0002_u2_session_security` creates the following; downgrade drops them in reverse:<br>- table `password_reset_tokens` (`reset_token_id`, `user_id`, `token_hash` unique, `issued_at`, `expires_at`, `used_at`);<br>- table `email_attempt_counters` (`email_hash`, `purpose`, `failed_count`, `locked_until`, `last_sent_at`, `flow_started_at`, `updated_at`; PK `email_hash, purpose`);<br>- columns `verification_attempts.flow_started_at`, `refresh_sessions.revoked_reason` and `refresh_sessions.attempt_hash`;<br>- the FK change;<br>- the indexes in performance design §2 |
| R-11 Background task | The task opens its **own** database session from the session factory. A final send failure supersedes **that code id only** (`WHERE id = :code_id AND consumed_at IS NULL`), so it never cancels a newer code. The sender is the U1 sync dispatcher run through `anyio.to_thread.run_sync` with the email `CapacityLimiter`, which keeps it off the event loop. A failed send does **not** reset `lastSentAt`, so the 60 s cooldown still holds and stops a send-failure loop |
