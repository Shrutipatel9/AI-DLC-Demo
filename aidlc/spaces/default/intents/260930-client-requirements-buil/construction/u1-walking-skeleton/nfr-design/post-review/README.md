# Post-Review Changes — NFR Design, U1 Walking Skeleton

The design files one folder up are kept exactly as the architecture reviewer saw them (review iteration 1, verdict NOT-READY; `../reviews/review-01.md`). The files in this folder are the **revised versions** that resolve that review's findings, written after the review. The human chose this arrangement on 2026-10-01.

The approved code generation plan (decisions D1–D13) and the code follow these revised versions, and the code review checked them in the code.

| Finding | Resolution (see the revised file) |
|---|---|
| R-01 Verify flow | `security-design.md` §2: follows WF-U1-2. Unknown user, no live code and wrong code give `CODE_INVALID`; only a found-but-expired code gives `CODE_EXPIRED`. The counter is upserted and then locked, with an expired lock reset first. The existence-signal risk is recorded as accepted |
| R-02 Thread pool | `reliability-design.md` §2: an email bulkhead (`CapacityLimiter(10)`, created in the lifespan), async health routes, and the 25 s deadline enforced around `smtplib` by a per-attempt timeout, a per-command budget check and a watchdog |
| R-03 Traceability targets | `logical-components.md` §5 (quality gates and CI jobs), the data classification table in `security-design.md` §6, and `traceability-revised.json` |
| R-04 CSP on the App Router | `security-design.md` §5: nonce propagation, dynamic rendering, matcher, development variant, runtime `API_ORIGIN` (implemented in `frontend/src/proxy.ts`, the Next.js 16 name) |
| R-05 Log allow-list | `observability-design.md` §2: adds `purpose`, `attempt`, `method` and `exception`, the `unmatched` route label, and a UUID-only request id |
| R-06 Docs and metrics routes | `security-design.md` §1: `PUBLIC_ROUTES`, `DEV_ONLY_ROUTES` and `OPERATIONAL_ROUTES`, with the route-enumeration test |
| R-07 Error code | `NOT_AUTHENTICATED` (C11) |
| R-08 Body guard | Sits after CORS; counts streamed bytes; returns 422 `VALIDATION_FAILED` / `BODY_TOO_LARGE` |
| R-09 Small gaps | Advisory lock per limiter key, rightmost-untrusted `X-Forwarded-For`, 2 h prune, active-`kid` start-up check, `CODE_HMAC_KEY` rotation note |
