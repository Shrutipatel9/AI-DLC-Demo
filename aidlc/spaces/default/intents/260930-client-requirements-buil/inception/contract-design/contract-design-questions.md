# Contract Design — Questions

This stage writes the **API documents**: the HTTP API between the Next.js frontend and the FastAPI backend (the public boundary: the browser is an outside consumer), the Stripe webhook, and the in-process interfaces between backend modules that different units build (`unit-of-work-dependency.md`).

Already fixed and not asked again:
- Endpoint names the client states: `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/change-password` (`AUTH-013`–`AUTH-016`).
- Status codes the client states: 402 for payment required (`FR-015`) and 409 for the photo identity mismatch (`BR-005`).
- The refresh token only ever travels as an httpOnly cookie (`FE-002`).
- Backend modules call each other in-process (units Q4).

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — URL layout
A. No version prefix, matching the client's paths exactly: `/auth/*`, `/onboarding/*`, `/photos/*`, `/payments/*`, `/analysis/*`, `/report/*`, `/images/*`, `/chat/*`, `/journey`, `/media/*` (Recommended)
B. Everything under `/api/v1/…` (the client's `/auth/*` paths become `/api/v1/auth/*` — a deviation to confirm with the client)
X. Other (please specify)

[Answer]: A

### Question 2 — Errors and status codes
A. One error format for every endpoint — `{"error": {"code", "message", "details", "requestId"}}` — with a fixed list of `code` values the frontend branches on. Status codes: 422 invalid input, 401 not signed in / bad code / bad token, 402 payment required, 404 not found or not yours, 409 identity mismatch or state conflict, 413/415 photo too big / wrong type, 429 code cooldown, code lockout and chat limit (with `Retry-After`), 502/504 upstream AI or Stripe failure (Recommended)
B. FastAPI's default `{"detail": …}` responses, codes chosen per endpoint
X. Other (please specify)

[Answer]: A

### Question 3 — JSON field names
A. camelCase in JSON (natural in TypeScript), with snake_case inside Python mapped automatically (Recommended)
B. snake_case in JSON everywhere
X. Other (please specify)

[Answer]: A

### Question 4 — Live updates (analysis progress, payment confirmation)
A. The browser polls a status endpoint every 2–3 seconds while the screen is open (simple, works on any host) (Recommended)
B. Server-Sent Events (server pushes updates)
C. WebSockets
X. Other (please specify)

[Answer]: A

### Question 5 — Chat replies
A. The whole reply is returned when it's ready (simpler; a "typing…" indicator covers the wait) (Recommended)
B. Stream the reply word by word
X. Other (please specify)

[Answer]: A

### Question 6 — Keeping frontend and backend in step
Both apps live in one repository and the frontend is the only consumer.

A. The backend publishes its OpenAPI document; the frontend's TypeScript types are generated from it and CI fails if they're out of date. Additive changes are free; a breaking change updates both apps in the same pull request (Recommended)
B. A formally versioned API with a deprecation period for every breaking change
X. Other (please specify)

[Answer]: A
