<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-10-01T11:45:40Z — u1-walking-skeleton: Next.js 16 renamed middleware.ts to proxy.ts, so the CSP lives in src/proxy.ts; the app starts from the create_app factory; local services use 127.0.0.1 because localhost stalls against Docker on Windows.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-10-02T07:29:02Z — u2-session-security: code review READY with 4 minor items left for a later fix: logout holds the cross-tab lock up to the 30 s request timeout (refresh is capped at 10 s); an over-long X-Refresh-Attempt header gives 422 instead of a cookie-clearing 401; the custom dialog keeps key handling on the dialog element only and its background is not inert; the coordinator never prunes its claims list.
- 2026-10-01T11:45:40Z — u1-walking-skeleton: code review R-01 (database errors can put the email and password hash into logs, because SQLAlchemy echoes statement parameters) needs a one-line engine fix plus a test; raise it at the skeleton checkpoint.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
