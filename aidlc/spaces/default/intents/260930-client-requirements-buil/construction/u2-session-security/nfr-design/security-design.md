# Security Design — U2 Session Security

**Sources:**
- `nfr-requirements/security-requirements.md`, read together with its `post-review-changes.md` (NFR2.1–NFR2.17, NFR3.x, NFR6.1)
- functional design, read together with its `post-review-changes.md`
- ADR-006
- U1 security design (the middleware stack, limiter, TokenService and cookie helpers are reused)

## 1. Refresh exchange (NFR2.1–NFR2.4, NFR2.6)

```text
POST /auth/refresh   (after CSRF check §3 and per-IP refresh limit)
parse cookie "tokenId.secret" → malformed: 401 INVALID
BEGIN
  s = SELECT refresh_sessions WHERE token_id=:id FOR UPDATE      -- serialises same-cookie races
  if s is None or not compare_digest(sha256(secret), s.secret_hash): 401 INVALID
  if s.revoked_at: 401 REVOKED
  if now >= s.expires_at: 401 EXPIRED
  if s.rotated_at:
     c = child of s
     if attempt_ok(header, c) and c unused and now - c.issued_at <= 60s:
        c.secret_hash = sha256(new_secret); COMMIT → 200 (recovered)        -- NFR2.3
     revoke family(s.family_id, reuse_detected); COMMIT → 401 REUSE_DETECTED
  s.rotated_at = now; c = new child(family, parent=s, attempt_hash=sha256(attempt_id)?)
COMMIT → 200 {accessToken, expiresAt} + Set-Cookie c
```

- **Recovery check (`attempt_ok`):** the header must be well-formed (22 base64url characters) and its SHA-256 must equal `c.attempt_hash`, compared in constant time. A missing or malformed id means "no id", so strict handling applies (NFR2.3, post-review R-03).
- **"Unused" child:** `c.rotated_at` and `c.revoked_at` are both empty. Every use of a session is a rotation, so an unused child has never been presented.
- **Row lock:** the lock on the parent row makes two concurrent exchanges of one cookie strictly ordered (NFR2.4).

## 2. Logout, reset and change revocation (NFR2.8, NFR2.10)

| Operation | Revocation scope | Transaction |
|---|---|---|
| Logout | `UPDATE refresh_sessions SET revoked_at, revoked_reason='logout' WHERE family_id = (family of cookie tokenId, rotated or not) AND revoked_at IS NULL` | single statement |
| Password reset | all usable sessions of the user, reason `password_reset` | with the password update and the reset-token use |
| Password change | all usable sessions of the user **except** the newest usable session of the cookie's family, and only when that family belongs to the Bearer user; reason `password_changed` | with the password update |

Cookie `Path=/auth` is enforced by a settings validator, so the change-password call carries the cookie (post-review R-03).

## 3. CSRF and CORS (NFR2.7, NFR2.17)
- **Dependency `require_csrf`** on `/auth/refresh` and `/auth/logout`:
  - it requires `X-Requested-With == "XMLHttpRequest"`;
  - it takes the origin from `Origin`, falling back to the scheme and host of `Referer`;
  - it refuses `null`, missing values and anything not in `CSRF_ALLOWED_ORIGINS`;
  - a refusal is 403 `CSRF_CHECK_FAILED`;
  - it runs before the cookie is parsed.
- **CORS** (U1 middleware, reconfigured):
  - `allow_origins = CSRF_ALLOWED_ORIGINS`;
  - `allow_credentials = True`;
  - `allow_headers = [Authorization, Content-Type, X-Requested-With, X-Refresh-Attempt, X-Request-ID]`;
  - `expose_headers = [Retry-After, X-Request-ID]`.
- **Cookie `SameSite`:** `Lax` when the frontend and API share a site. A cross-site deployment needs `None` together with `Secure`, and the validator enforces that pairing.

## 4. Reset tokens (NFR2.9)
- **Issue:** `secrets.token_urlsafe(32)`; only `sha256` is stored; earlier unused tokens of the user are marked used in the same transaction.
- **Consume:**
  - `UPDATE password_reset_tokens SET used_at=now WHERE token_hash=:h AND used_at IS NULL AND expires_at > now RETURNING user_id`;
  - zero rows → 401 `RESET_TOKEN_INVALID`.
- **Never a Bearer token:** the reset token is not a JWT. A Bearer value that fails JWT parsing is a plain 401 `NOT_AUTHENTICATED`.

## 5. Anti-enumeration (NFR2.11, NFR2.16)
- **Non-revealing handlers** (forgot; resend for `login` and `password_reset`):
  1. compute the email hash `HMAC(EMAIL_HASH_KEY, normalised email)`;
  2. upsert the shadow or account counter;
  3. decide `send = True/False`;
  4. return 202 `CodeSent` (`maskedEmail`, `resendAvailableAt = now + 60 s`, `expiresAt = now + 10 min`);
  5. only after that, `BackgroundTasks.add_task(send_code, ...)` when `send`.
- **Same work on every branch:** both branches perform one HMAC, one upsert and one response build.
- **Verify for an unknown email** (`login`, `password_reset`): use the `EmailAttemptCounter` with the same transaction shape as the account counter (U1 D5). After 5 failures it returns 429 `CODE_LOCKED`, the same as a real account.

## 6. Throttling (NFR2.13 + post-review R-04)

| Endpoints | Limit (per IP, sliding minute) |
|---|---|
| register, login, verify, resend-code, forgot, verify-code, reset, change-password | `AUTH_RATE_LIMIT_PER_MINUTE` (20) |
| refresh, logout | `REFRESH_RATE_LIMIT_PER_MINUTE` (60) |

Responses over the limit are 429 `RATE_LIMITED` with `Retry-After` (U1 PostgreSQL limiter).

## 7. Client-side security (NFR2.14, NFR2.15)
- **Generation-tagged store:** each refresh captures `generation` at its start; `logout()` and a broadcast `signedOut` increment it; a result whose generation is stale is discarded, so a late refresh can never revive a signed-out tab.
- **Attempt id:** `crypto.getRandomValues(new Uint8Array(16))` → base64url. It is created per refresh operation, reused only for that operation's single retry, and held in a closure. It is never placed in the store, broadcast or logged.
- **BroadcastChannel payload:** `{type:"refreshed", accessToken, expiresAt, user, at}` or `{type:"signedOut", reason}`. Messages are same-origin only. The refresh secret never leaves the httpOnly cookie.
- **401 handling:** the API client's 401 handler matches only the code `NOT_AUTHENTICATED`.

## 8. Logging safety (NFR3.1, NFR3.2, NFR5.12)
- The SQLAlchemy engine is created with `hide_parameters=True`. This also fixes the U1 code-review finding R-01.
- The log formatter allow-list gains `familyId`, `reason`, `count` and `outcome`.
- Reset tokens, attempt ids, email hashes and cookie values never appear in logs; a canary test seeds each one.
