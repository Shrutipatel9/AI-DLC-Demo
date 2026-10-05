# NFR Design — U1 Walking Skeleton — Questions

The NFR requirements already settle most of the design: email sent outside any transaction, a PostgreSQL-backed limiter, JSON logs with request ids, and opt-in metrics. Three design choices remain open.

Pick one letter per question (or X and describe your own answer).

---

### Question 1 — Protecting sign-in from a failing email provider
Email is the only outside service in this unit. Each send already has a 25 s budget, retries with backoff, and an hourly cap.

A. No circuit breaker yet. When the provider is down, each request fails within its budget with a clear "try again" message. Add a breaker when there is real traffic (Recommended)
B. Add a circuit breaker now: after 5 consecutive failures, fail fast for 30 s, then probe with one request
X. Other (please specify)

[Answer]: A

### Question 2 — Request tracing depth
A. A request id on every request and log line, returned in the `X-Request-ID` header and in error bodies. Full distributed tracing (OpenTelemetry) is deferred until hosting and the worker exist (Recommended)
B. Add OpenTelemetry tracing now (FastAPI, SQLAlchemy and outgoing HTTP), exported to the console locally
X. Other (please specify)

[Answer]: A

### Question 3 — Content-Security-Policy for the Next.js app
A Next.js App Router page needs inline scripts to start up, so a strict policy needs a per-request nonce.

A. Strict nonce-based CSP set by Next.js middleware: `script-src 'self' 'nonce-…' 'strict-dynamic'`, with `connect-src` limited to the API origin. Pages render per request, which is fine for these small pages (Recommended)
B. Static CSP header in `next.config` allowing `'unsafe-inline'` scripts (simpler, weaker XSS protection)
X. Other (please specify)

[Answer]: A
