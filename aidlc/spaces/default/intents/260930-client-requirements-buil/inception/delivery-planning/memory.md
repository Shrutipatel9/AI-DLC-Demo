<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-30T13:22:38Z — With a near-linear dependency chain, applied risk-first inside Bolts (test-first auth, photo calibration, real-vendor AI evaluation and a timed image run) rather than by reordering units.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-30T13:22:38Z — Deferred the verification command to the first checkpoint because no code exists yet; Bolt 1 creates it and the human approves it there.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-30T13:22:38Z — Declined an early throwaway image-generation spike to avoid needing the OpenAI key before Bolt 6; offered it at the gate as an optional add.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
