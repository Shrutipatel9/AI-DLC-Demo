<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
- 2026-09-30T09:55:34Z — Kept the client IDs as the source of truth and added a separate FR/NFR numbering mapped to them, so later stages get stable workflow IDs without renaming the client document.
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->

## Deviations
- 2026-09-30T09:55:34Z — Narrowed FR-008 (answers sent to OpenAI as context) to non-medical answers per the human decision on Q1; recorded as a delivery-team decision the client must confirm.
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->

## Tradeoffs
- 2026-09-30T09:55:34Z — Publishing a report with a failed image marked as not available (Q6) keeps the report on time at the cost of an occasional missing after-image; chose it over holding the whole report hostage to one vendor call.
- 2026-09-30T09:55:34Z — Tier labelling by OpenAI structured output with keyword fallback (Q3) trades a small prompt change for better accuracy than keyword rules alone.
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->

## Open questions
- 2026-09-30T09:55:34Z — Jurisdiction for biometric and health data and the multi-tab refresh race remain open; carried into Open Questions for the client and domain design.
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
