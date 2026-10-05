# Security Requirements — U2 Session Security

**Sources:**
- `requirements.md`: NFR2 (authentication security), NFR3 (data protection), NFR6 (configuration).
- Client IDs: `AUTH-010`–`AUTH-016`, `FE-002`, `FE-005`, `FE-006`.
- ADR-006.
- U2 functional design: `rules.md`, read together with `post-review-changes.md` (that note amends the rules and wins on conflict).
- U1 security requirements: inherited unchanged unless restated here.

IDs extend the inception NFRs and are numbered for this unit.

## 1. Sessions and tokens (NFR2)

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR2.1 | **Refresh rotation:** every successful refresh replaces the session with a child in the same family. The old session can never be exchanged again (`AUTH-012`, BR2.1). | Integration test: a second exchange of the parent is refused. |
| NFR2.2 | **Strict reuse detection:** a replayed rotated session (without the matching attempt id; see NFR2.3) revokes the whole family. The response is 401 `SESSION_INVALID` with reason `REUSE_DETECTED`. There is no time-based grace window (ADR-006, BR2.3). | Test: replay from a second client gives 401 and every family member is revoked. |
| NFR2.3 | **Lost-response recovery:** a rotated session presented again with the same `X-Refresh-Attempt` id (128-bit, random, kept in tab memory only), within 60 s, while the child is unused, re-issues that child with a new secret. Any other replay follows NFR2.2 (post-review R-04). | Tests: lost response, then retry with the same id → 200. A different id, no id, after 60 s, or after the child was used → family revoked. |
| NFR2.4 | **Atomic refresh:** exchanging a session is one transaction with a row lock on the session, so two concurrent exchanges of one cookie give exactly one child (WF-U2-5). | Concurrency test: 2 parallel refreshes give 1 child + 1 reuse outcome, or 1 child + 1 attempt-id re-issue when the same id is used. |
| NFR2.5 | **Cookie:** the refresh cookie is `HttpOnly`, `Max-Age` 7 days, `Path=/auth` (enforced by the settings validator), with `SameSite` and `Secure` from configuration. Every response that ends a session sends `Max-Age=0` (BR2.8, R-03). | Header assertions on verify, refresh, logout and refused refresh. Settings test: a `Path` other than `/auth` refuses to start. |
| NFR2.6 | **Storage:** only `tokenId` and SHA-256 of the 32-byte secret are stored. Secrets are compared in constant time (`AUTH-010`, BR2.7). | Database inspection test; a code check for `compare_digest`. |
| NFR2.7 | **CSRF on cookie endpoints:** `/auth/refresh` and `/auth/logout` require `X-Requested-With: XMLHttpRequest`, and an `Origin` (or `Referer` when `Origin` is absent) on the allow-list. Missing headers, `Origin: null`, or no allow-listed origin give 403 `CSRF_CHECK_FAILED`. No session is read or changed (`AUTH-013`, BR2.5, R-08). | Parameterised test over header combinations; the session is unchanged afterwards. |
| NFR2.8 | **Logout:** revokes every session of the family named by the cookie, even if that session was already rotated. It always clears the cookie and returns 204 (BR3.1, R-02). | Tests: logout with a rotated cookie revokes the live child; a replay then gives 401 `REVOKED`. |
| NFR2.9 | **Reset token:** 256 bits from a CSPRNG, base64url-encoded, stored as SHA-256. It is valid for the configured window (10 min). It is single use, enforced by an atomic conditional update with a row-count check. It never parses as an access token (`AUTH-015`, BR4.3, BR4.4, R-09). | Tests: expiry at 9:59 and 10:00; reuse; two concurrent resets give one success; Bearer use gives 401. |
| NFR2.10 | **Revocation on credential change:** a reset revokes every session of the account (BR4.6). A change keeps the current session, resolved through its family and the Bearer-user match, and revokes all others (BR5.3, R-03). **Accepted residual risk:** access tokens already issued elsewhere stay valid for up to 15 minutes (`AUTH-002`). | Integration tests across 3 simulated devices. |
| NFR2.11 | **Anti-enumeration:** forgot-password, and resend for the purposes `login` and `password_reset`, always answer 202 with the same shape, including during cooldown and lockout. Verify for an unknown email uses an email-keyed shadow counter, so lockout behaves the same. The email is sent after the response (BR1.5, BR4.1, R-01). | Paired tests: a real and a fake email give identical status codes and bodies over 7 sequential calls. Timing check: the response p95 differs by less than 50 ms. |
| NFR2.12 | **Lockout:** 5 wrong codes per account (or email hash) and purpose lock that purpose for 15 minutes. While locked, codes and (visible) resends are refused, and a resend never resets the count (`AUTH-011`, BR1.3, BR1.4). | Injectable-clock tests at L+14:59 and L+15:00. |
| NFR2.13 | **Throttling:** the per-IP limiter (U1) also covers resend-code, forgot, verify-code, reset and change-password. It answers 429 `RATE_LIMITED` with `Retry-After` (R-10). | Test: the 21st call within a minute gives 429 for each endpoint. |

## 2. Browser and client (NFR2, FE-*)

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR2.14 | No token, profile or auth flag in Web Storage, IndexedDB or a persisted store. Tabs share only the access token and profile, over the same-origin `BroadcastChannel` (`FE-002`, BR6.8). | Vitest test plus a Playwright storage assertion after restore, refresh and two-tab use. |
| NFR2.15 | Only `NOT_AUTHENTICATED` triggers refresh-and-retry. Other 401 codes (`INVALID_CREDENTIALS`, `CODE_*`, `RESET_TOKEN_INVALID`, `SESSION_INVALID`) never do (BR6.4). | API-client tests per code. |
| NFR2.16 | Every confirmation and error message is generic. No message reveals whether an email exists, except the client-mandated `EMAIL_ALREADY_REGISTERED` on sign-up. | Copy review checklist plus the paired tests in NFR2.11. |

## 3. Data protection and logging (NFR3, NFR5)

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR3.1 | **Classification:** reset tokens, refresh secrets, attempt ids and email hashes are **Restricted**. They are never logged or returned except the one-time reset token in the verify-code response. | Log canary test that seeds each value. |
| NFR3.2 | **Database parameters in logs:** the engine is created with `hide_parameters=True`, so database errors never put emails or hashes into logs (carries U1 code-review R-01 into U2's work). | Test: a forced integrity error writes no email or hash to the captured logs. |
| NFR5.12 | **Security events (answer Q2):** logged as structured events, with the user id or a masked email and never secrets. WARN: `auth.session.reuse_detected` (family id), `auth.code.locked`. INFO: `auth.session.refreshed` (debug-sampled), `auth.logout`, `auth.password.reset_requested`, `auth.password.reset`, `auth.password.changed`, `auth.sessions.revoked` (count, reason). No database table. | Log-capture test per event. |

## 4. Configuration (NFR6)

| ID | Requirement | Pass/fail check |
|---|---|---|
| NFR6.1 | New settings, all typed, with defaults where shown: `REFRESH_TOKEN_DAYS` (7), `RESET_TOKEN_MINUTES` (10), `REFRESH_ATTEMPT_RECOVERY_SECONDS` (60), `CSRF_ALLOWED_ORIGINS` (defaults to `FRONTEND_ORIGIN`), `EMAIL_HASH_KEY` (required, at least 32 bytes). | Settings tests: defaults, plus a refusal when `EMAIL_HASH_KEY` is missing or short. |

## 5. Threat model additions (STRIDE)

| Threat | Example | Mitigation |
|---|---|---|
| Spoofing | Stolen refresh cookie replayed | NFR2.1, NFR2.2. The attempt id never leaves tab memory, so NFR2.3 does not help a thief. |
| Spoofing | Brute-forcing the reset code | NFR2.12 lockout, NFR2.13 throttle, shadow counter |
| Tampering | Forged reset token | 256-bit random value with a hashed lookup (NFR2.9) |
| Repudiation | A user disputes a password change | `auth.password.changed` log event with the request id |
| Information disclosure | Email enumeration via forgot, resend or verify | NFR2.11, NFR2.16 |
| Denial of service | Locking a victim's account by guessing codes | Accepted: the client-mandated lockout (`AUTH-011`) is per account. It is limited by the per-IP throttle, and a lockout blocks codes only, not password login steps. |
| Elevation of privilege | Using a reset token as Bearer | NFR2.9: opaque token, not a JWT |
| CSRF | Forced logout or refresh from another site | NFR2.7 |
