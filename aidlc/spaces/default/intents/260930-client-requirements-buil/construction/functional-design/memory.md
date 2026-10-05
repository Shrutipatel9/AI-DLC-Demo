<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-10-01T12:30:34Z — u2-session-security: kept the contract's 401 INVALID_CREDENTIALS for a wrong current password and made the API client treat only NOT_AUTHENTICATED as an expired session, so a typo never triggers a refresh loop.
- 2026-10-01T04:27:33Z — u1-walking-skeleton: treated an unverified account at login as invalid credentials (generic message) and pointed users to re-sign-up, which re-sends the code, to avoid revealing account state.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-10-01T12:30:34Z — u2-session-security: a login resend is honoured only within 10 minutes of a successful password step, so resend can never be used to skip the password check.
- 2026-10-01T04:27:33Z — u1-walking-skeleton: built the per-account failed-code counter in U1 even though its lockout screens are U2, so a resend can never reset the count and U2 needs no schema change.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
