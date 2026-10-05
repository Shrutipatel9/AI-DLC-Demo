<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-30T12:06:54Z — Treated the frontend auth store and the UI as two components so the client-mandated layering (UI, auth store, API client, backend auth) is visible in the catalogue; infrastructure and vendors stay external dependencies.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-30T12:06:54Z — Added an ADR-007 rule not asked as a question: medical answers are only readable inside Onboarding, enforcing the Q1 requirements decision structurally rather than in each prompt.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-30T12:06:54Z — Chose strict server reuse detection with browser-tab coordination (Q6) over a grace window; keeps AUTH-012 exact at the cost of subtle client code that must be test-first.
- 2026-09-30T12:06:54Z — Journey fans out to five components per request to avoid a second stored copy of progress (Q3).
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
