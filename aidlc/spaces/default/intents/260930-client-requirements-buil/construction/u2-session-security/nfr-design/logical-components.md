# Logical Components — U2 Session Security

**Sources:** the NFR design files in this folder; `tech-stack-decisions.md` (NFR1.1, NFR7.1, NFR8.1–NFR8.3); the U1 logical components.

## 1. New and extended components

| Component | Kind | Owns | NFR patterns | Failure domain |
|---|---|---|---|---|
| Identity `sessions` service | Backend module | Refresh exchange, recovery, family revoke, logout | Row lock, attempt hash, strict reuse | One user's family |
| Identity `password_reset` service | Backend module | Forgot, verify-code, reset token, reset | Shadow counters, email after the response, atomic consume | One account |
| Identity `password_change` service | Backend module | Change and revoking other sessions | One transaction | One account |
| Identity `cleanup` command | CLI | Deleting old rows | Batched, idempotent | None (offline) |
| `require_csrf` dependency | Backend platform | Origin/Referer and header check | Fails before the cookie is read | One request |
| WebAuthClient `refreshCoordinator` | Frontend module (private to `lib/auth`) | Single flight, lock, broadcast, attempt id, generation | Bulkhead per tab, 10 s timeout | One browser |
| WebApp toast service and confirm dialog | Frontend shared UI | Feedback and confirmation | Accessible live regions, focus trap | One tab |
| Migration `0002_u2_session_security` | Database | New tables, columns and indexes | Clean downgrade | — |

## 2. Dependency direction (lint-enforced, NFR7.1)
- **Backend:** routes call services; services call repositories and platform ports. `sessions`, `password_reset` and `password_change` may use `codes` and `tokens` (U1). Routes never import repositories or tokens directly; the import-linter contracts are extended to cover this.
- **Frontend:** `app/*` and `components/*` call only `useAuth()` selectors and actions, plus `toast` and `confirm`. `refreshCoordinator` and the store setters are importable only inside `lib/auth`.

## 3. Shared resources and blast radius

| Resource | Shared by | Risk | Isolation |
|---|---|---|---|
| `auth-refresh` browser lock | All tabs of one browser | A hung holder blocks the other tabs | 10 s fetch timeout; the lock is released in `finally` |
| `refresh_sessions` rows | All tabs and devices of one user | Lock waits | Per-row lock, short transactions |
| Email bulkhead (10) | All code sends | Slow sends | Sending after the response, so request threads are never held |

## 4. Tests and verification (NFR8.1–NFR8.3)
- **Test-first:** backend `sessions` and `password_reset`; frontend `refreshCoordinator` (single flight, retry, cross-tab, generation).
- **Playwright journey** `e2e/session.spec.ts`, added to `scripts/verify-skeleton.sh` and CI, covers:
  - reload stays signed in;
  - two tabs refresh at the same time;
  - logout broadcast;
  - forgot → Mailpit code → reset → login;
  - change password.
- **Migration round-trip:** `0002` is included in the existing CI and checkpoint round-trip.
