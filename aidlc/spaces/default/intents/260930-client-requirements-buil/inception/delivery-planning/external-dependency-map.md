# External Dependency Map — AI Facial Analysis Platform

These are the things the build needs from outside the team, mapped to the **Bolt** that first needs each one. A Bolt is one build pass over a piece of the work that ends in something that runs (see `bolt-plan.md`).

**Rule (delivery Q5):** build against fakes until a real service is needed. The default test run never calls a paid service (project Forbidden rules). Client confirmations are chased in parallel and do not block Bolts, because the affected content is configurable.

## Accounts, keys and tools

| Dependency | Owner | Lead time (estimate) | Needed by | Blocks | If it slips |
|---|---|---|---|---|---|
| GitHub repository admin access (branch protection, Actions, Dependabot) | You / repository owner (`Shrutipatel9/AI-DLC-Demo`) | Immediate | Bolt 1 | Bolt 1 Definition of Done (protected `main`) | Build proceeds; protection is enabled before Bolt 1 is approved |
| Docker on the development machine | You | Immediate | Bolt 1 | Local PostgreSQL and mail catcher | Use a locally installed PostgreSQL (documented alternative) |
| Stripe test-mode account + API keys + Stripe CLI | Client / you | ~1 day | Bolt 5 | Real checkout demo | Build with the Stripe fake; demo waits for keys |
| OpenAI API key with a monthly budget limit (`gpt-4o`, `gpt-image-1` access) | Client (costs are the client's, `BR-006`) | ~1 day; image-model access may need account verification | Bolt 6 | Real-model evaluation (Bolt 6), timed run and cost check (Bolt 7) | Build with fakes; evaluation and timing checks move to when the key arrives, and the Bolt 6/7 approvals wait for them |
| Consented, diverse test photo set (for calibration and evaluation) | Delivery team with the client's agreement | ~1 week | Bolt 4 | Threshold calibration | Calibrate on a smaller set; flag the tuning pass as open |
| Email provider (SendGrid, AWS SES, Postmark…) | Client / delivery team (`NFR-012`) | ~1–3 days | Before first real deployment (not in this workflow) | Nothing in this workflow | Local mail catcher throughout |
| Hosting | Client (`NFR-010`) | Undecided | Not in this workflow | Nothing | — |

## Client confirmations

| Item | Source | Needed by | Blocks | If it slips |
|---|---|---|---|---|
| The 23-question specification's open items: Q9/Q11 follow-up shape, Q19 condition | [QS] §5 | Bolt 3 | Final questionnaire content only | Ship the working-spec reading; change it later in seed data |
| Medical-flag list (Q8–Q12 + follow-ups) | Stories AC4.4.3 | Bolt 3 | Nothing (the conservative list is used) | Keep the conservative list |
| Consent wording and the "can't confirm disclaimer" message | Requirements Q2, stories Q13 | Bolt 3 | Final wording only | Ship recommended wording, configurable |
| 3 photo angles vs the 7-pose reference (`OQ-010`) | `ASM-005` | Bolt 4 | Nothing (angle set is configurable) | Keep 3 angles |
| Report price (`OQ-002`) | `FR-016` | Bolt 5 | Nothing (price is configurable) | Use a placeholder test price |
| Recommendation tiering method (`OQ-012`) | Requirements Q3 | Bolt 6 | Nothing | AI labelling with keyword fallback |
| User jurisdictions (biometric and health-data rules) | Requirements Q2 | Before launch | Nothing in this workflow | Consent step already in place |
| Report specification TBD items (protocol phases, facial age, priority-feature rule) | [RD] §20 | Bolt 8 | Those dashboard items only | Omit TBD items |
| Whether the knowledge-folder drafts are the official specifications | Stories Q7 | Bolt 3 onward | Nothing | Treat them as working specifications |

## Summary
No external item blocks Bolts 1–4. Bolt 5 needs Stripe test keys for its demo, and Bolts 6–7 need the OpenAI key for their real-model checks. Everything else is configurable content that can change after the build.
