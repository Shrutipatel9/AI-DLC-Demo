<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-10-01T12:40:26Z — u2-session-security: carried the U1 code-review logging finding (database parameters in error logs) into U2 as NFR3.2, so it gets fixed with this unit's code.
- 2026-10-01T04:39:55Z — u1-walking-skeleton: the inception requirements have no sign-in latency target, so the new auth latency targets (NFR Q6) are filed under NFR9 as their closest parent, with that origin stated.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-10-01T04:44:29Z — u1-walking-skeleton: after the review I added NFR5.13 (no email send inside a transaction or while holding a connection), an hourly cap on code emails, HMAC binding to user and purpose, and HSTS; none of these were asked for in the questions.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-10-01T04:39:55Z — u1-walking-skeleton: per-IP throttling stores its window in PostgreSQL behind an interface instead of adding Redis; this keeps the skeleton free of new infrastructure at a small cost per auth request.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-10-01T04:39:55Z — u1-walking-skeleton: the launch volume (100 sign-ups per hour, 50 concurrent users) is an assumption; confirm with the client once hosting is chosen.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
