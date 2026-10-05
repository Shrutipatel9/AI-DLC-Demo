<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-10-01T04:51:57Z — u1-walking-skeleton: read NFR5.13 as commit, then send, then compensate in a second transaction, not as a background job; U1 has no worker yet.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-10-01T05:02:36Z — u1-walking-skeleton: an oversized auth body returns 422 VALIDATION_FAILED (reason BODY_TOO_LARGE) instead of 413, because the contract has no generic too-large code.
- 2026-10-01T04:51:57Z — u1-walking-skeleton: the perf test uses 50 measured samples instead of the 10 in the requirement, a stricter measurement of the same p95 target.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-10-01T13:04:40Z — u2-session-security: lost-response recovery uses a per-call attempt id held only in tab memory; it keeps strict reuse detection against stolen cookies while avoiding false revocations on flaky networks.
- 2026-10-01T05:02:36Z — u1-walking-skeleton: verify can reveal that an account exists (attemptsLeft, lock, expiry); accepted because sign-up already reveals registration by client rule, and probing is throttled.
- 2026-10-01T04:51:57Z — u1-walking-skeleton: the nonce CSP makes pages render per request; we accept a few ms of server render for strong protection against injected scripts.
- 2026-10-01T04:51:57Z — u1-walking-skeleton: no circuit breaker on email for now (human choice); requests fail within their 25 s budget instead of failing fast.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
