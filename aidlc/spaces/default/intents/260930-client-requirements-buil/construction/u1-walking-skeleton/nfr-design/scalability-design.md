# Scalability Design — U1 Walking Skeleton

**Sources:** `nfr-requirements/scalability-requirements.md` (NFR11.1–NFR11.5) and `tech-stack-decisions.md`.

## 1. Approach: stateless processes, state in PostgreSQL
- **Web process (FastAPI/Uvicorn):** holds no per-user state in memory. Tokens are self-contained (JWT), and everything else — codes, counters, sessions, limiter hits — is in PostgreSQL (NFR11.1, NFR11.3). Any number of instances can sit behind a round-robin load balancer, with no sticky sessions.
- **Frontend (Next.js):** stateless server rendering; auth state lives in the browser tab's memory only.
- **Worker process:** not used in U1. It arrives in U6 and will read jobs from PostgreSQL, so the same statelessness rule applies.

## 2. Shared-state components and their scaling path

| Component | U1 implementation | Works across instances because | Replace when |
|---|---|---|---|
| Per-IP limiter (NFR11.2) | PostgreSQL table behind the `RateLimiter` port | All instances write and count the same table | Write load from hits becomes noticeable (more than about 50 req/s on auth): swap in a Redis adapter, with no caller changes |
| Code and attempt counters (NFR11.3) | PostgreSQL with row locks | Locks are database-wide | Not expected to need change |
| Unique email (NFR11.3) | Unique index on `lower(email)` | Enforced by the database | — |
| Signing keys | Environment configuration, identical on all instances | Same `JWT_SIGNING_KEYS` everywhere | Moves to a secrets manager when hosted |

## 3. Capacity at the planning assumption (NFR11.5)
At 100 sign-ups per hour and 50 concurrent users, auth peaks at about 2 req/s. One web process (40 threads, a pool of 5 + 5 connections) handles this with large headroom: about 10 Argon2 operations per second per core.

**Scale triggers to adopt when hosted:**
- p95 of auth over 400 ms for 15 minutes → add an instance;
- pool wait over 100 ms → raise the pool size, staying within PostgreSQL `max_connections`.

These triggers are recorded for the Operation phase.

## 4. Configuration-only differences (NFR11.4)
All values that differ between environments are settings: database URL, pool sizes, frontend origin, cookie attributes, trusted proxies, limiter limits, email backend and caps, log level, and metrics on/off. No module reads the host name or assumes a cloud provider.

## 5. Data growth
| Table | Growth | Cleanup |
|---|---|---|
| `users` | One per sign-up | None (client defines no retention, §2.2) |
| `one_time_codes` | About 1–3 per sign-up or login | Maintenance command in U2 deletes rows older than 30 days |
| `refresh_sessions` | One per login | U2 command deletes expired or revoked rows older than 30 days |
| `rate_limit_hits` | One per auth request | Self-pruned by the limiter (rows older than 1 h) |
| `verification_attempts` | At most 2 per user (purposes) | None needed |
