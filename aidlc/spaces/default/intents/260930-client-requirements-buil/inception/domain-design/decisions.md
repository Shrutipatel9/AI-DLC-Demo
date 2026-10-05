# Architecture Decisions — Domain Design

Architecture Decision Records for the component design in `components.md`. Each ADR follows the inception rule: Context, Decision, Consequences, Alternatives Rejected, plus the security and compliance implications for significant decisions. The answers referenced are in `domain-design-questions.md` (Q1–Q6).

| ADR | Title | Status |
|---|---|---|
| ADR-001 | Split analysis into measurement, writing, images and report, coordinated by a pipeline | Accepted |
| ADR-002 | A shared, stateless Face Geometry block | Accepted |
| ADR-003 | Next step computed read-only by Journey | Accepted |
| ADR-004 | Payments answers entitlement; nothing else owns payment state | Accepted |
| ADR-005 | Every external service behind a port-and-adapter, selected by configuration | Accepted |
| ADR-006 | Browser tabs coordinate refresh; server reuse detection stays strict | Accepted |
| ADR-007 | Medical answers never leave Onboarding | Accepted |
| ADR-008 | Frontend organised as feature folders mirroring the backend | Accepted |
| ADR-009 | One private MediaStore for every face image and PDF | Accepted |
| ADR-010 | Report text and the published report are separate owners | Accepted |

---

## ADR-001: Split analysis into measurement, writing, images and report, coordinated by a pipeline

## Status: Accepted

**Context.** After "Start Analysis" four distinct kinds of work run:
- CV measurement (MediaPipe/OpenCV, `FR-007`);
- AI text (gpt-4o, `FR-008`);
- 24 AI images (gpt-image-1, `FR-020`/`FR-022`);
- report assembly and the PDF (`FR-009`–`FR-014`).

They change for different reasons: CV tuning (`ASM-010`), prompt changes, an image vendor swap (`NFR-013`), and design changes ([RD]). The run must resume without repeating paid calls, allow exactly one analysis per payment plus one free re-run (stories Q8), and finish within 10 minutes (NFR4).

**Decision.** FaceMeasurement, ReportWriting, ImageGeneration and Report are separate components. AnalysisPipeline owns `AnalysisRun`/`RunStep`, the step order, resume, the re-run policy and progress, and calls the four in order (Q1 = A).

**Consequences.**
- *Positive:*
  - Each piece is testable alone with fakes.
  - Vendor or prompt changes stay inside one block.
  - Resume is designed in one place.
  - Progress steps map one-to-one to components.
- *Negative:*
  - More interfaces to define (Contract Design).
  - The pipeline becomes a hub with many dependencies, so its interface must stay thin.
- *Neutral:* how these are deployed (one backend process plus a worker, or more) is left to Units Generation.

**Alternatives rejected.**
- *One "Analysis" block* — simpler at first, but mixes four change rates, makes resume logic tangle with vendor code, and blocks testing CV without AI fakes.
- *Event choreography without an orchestrator* — no single owner of run state; harder to guarantee "one run per payment" and to show accurate progress.

**Security and compliance.** The pipeline is the only place that assembles cross-component inputs for AI, so the privacy filter must be enforced upstream (ADR-007) rather than trusted here. Run records hold no photo bytes or answer text, only references.

---

## ADR-002: A shared, stateless Face Geometry block

## Status: Accepted

**Context.** Landmark detection is used by the per-photo checks (face count, pose, occlusion), the same-person signature (`ASM-010`, [IV]) and the measurements (`FR-007`). If each re-implements it, results can disagree (a photo passes validation with one landmark set and is measured with another), and the model is loaded twice.

**Decision.** FaceGeometry is its own stateless component (landmarks, pose, identity signature, pairwise distance), used by PhotoIntake and FaceMeasurement (Q2 = A). It caches the model object only, never results ([IV] §5).

**Consequences.**
- *Positive:*
  - One pinned model version.
  - Consistent outputs.
  - Deterministic results make the scores reproducible (AC7.3.2).
- *Negative:* one more module boundary. CPU-heavy calls must run outside the request thread (a concern for the NFR and design stages).

**Alternatives rejected.** *Landmarks inside PhotoIntake, with FaceMeasurement calling PhotoIntake* — this would make measurement depend on the upload component and couple two different change rates.

**Security and compliance.** Pure computation on images already stored privately; it keeps nothing, so it adds no new place where biometric data rests.

---

## ADR-003: Next step computed read-only by Journey

## Status: Accepted

**Context.** Every entry point must send the user to the right step, and an inconsistent photo set must always route back to photos (`BR-005` rule 7, US11.8). The state already lives in Onboarding, PhotoIntake, Payments, AnalysisPipeline and Report.

**Decision.** Journey owns no data. It queries each owner and applies the fixed order in `components.md` (Q3 = A).

**Consequences.**
- *Positive:*
  - There is no second copy of the state that could drift (for example, "photos done" stored while a retake made the set inconsistent).
  - One parametrised test covers the whole table.
- *Negative:* one request fans out to five components. This is cheap within one backend process and can be revisited if they are split later.

**Alternatives rejected.** *A stored progress record owned by Identity, updated by every component* — duplicate state, ordering bugs on retakes, and every component would need to write to Identity.

**Security and compliance.** Returns only a step name, never the underlying data.

---

## ADR-004: Payments answers entitlement; nothing else owns payment state

## Status: Accepted

**Context.** Payment status may change only through the verified Stripe webhook, and analysis starts only on the user's click (`FR-015`). Both the pipeline (402 on start) and Report (402 on read) need to know whether the user has paid.

**Decision.** Payments owns `Payment` and `ProcessedWebhookEvent` and exposes an entitlement query; AnalysisPipeline and Report call it (Q4 = A). The webhook updates payment status only.

**Consequences.**
- *Positive:*
  - One source of truth for payment.
  - The webhook stays small and idempotent.
  - The client rule "the webhook never starts analysis" is structurally true.
- *Negative:* the pipeline and Report depend synchronously on Payments; both are in the same trust boundary, so this is acceptable.

**Alternatives rejected.** *The webhook creates a "ready to analyse" run* — spreads payment knowledge into the pipeline, blurs "paid" and "started", and makes the re-run policy harder to reason about.

**Security and compliance.** Webhook signature verification against the raw body and idempotency by event id live in Payments only. No card data ever touches the platform (Stripe hosted Checkout).

---

## ADR-005: Every external service behind a port-and-adapter, selected by configuration

## Status: Accepted

**Context.** The client requires the OpenAI base URL, key and model to be configuration (`NFR-008`) and the image vendor to be swappable (`NFR-013`). The email provider and hosting are undecided (`NFR-012`, `NFR-010`). The team forbids paid calls in default tests (project Forbidden rules).

**Decision.** OpenAI text, image generation, Stripe, email and file storage are each reached through an interface defined by the owning component, with a real adapter and a test fake, chosen by configuration.

**Consequences.**
- *Positive:*
  - Vendor swaps change one adapter.
  - Tests run offline and free.
  - Secrets are needed only when a real adapter is selected.
- *Negative:* a little extra code per vendor, plus the discipline to keep vendor types out of domain code.

**Alternatives rejected.** *Calling vendor SDKs directly from components* — this breaks `NFR-013`, forces real keys in tests, and spreads vendor quirks across the codebase.

**Security and compliance.** Adapters are the single place for timeouts, retries and redaction, so no photo bytes or answers are logged. Keys come only from configuration or a secrets manager.

---

## ADR-006: Browser tabs coordinate refresh; server reuse detection stays strict

## Status: Accepted

**Context.** `AUTH-012` requires that reusing an already-rotated refresh token revokes the whole token family. `FE-006` forbids logging a user out for anything other than an invalid refresh session or an explicit logout. Two tabs refreshing at the same moment send the same cookie twice, which is indistinguishable from reuse and would log the user out (US3.11, product-lead finding R-04).

**Decision.** WebAuthClient coordinates across tabs: one tab holds a browser lock (Web Locks API, with a BroadcastChannel fallback) and performs the refresh, and the other tabs wait for and reuse its result. The server keeps reuse detection fully strict, with no grace window (Q6 = A).

**Consequences.**
- *Positive:* the client's security rule is kept exactly as written, and ordinary multi-tab use doesn't log people out.
- *Negative:*
  - The coordination logic is subtle, so it is test-first (team practices).
  - A browser without Web Locks or BroadcastChannel (very old) falls back to per-tab refresh, where the race is still possible. This is accepted given the supported browsers (NFR9).

**Alternatives rejected.**
- *A server grace window (~10 s)* — simpler, but weakens reuse detection: a stolen token replayed within the window would not revoke the family.
- *Both* — adds the weakness of the grace window for little extra benefit.

**Security and compliance.** The strongest reading of `AUTH-012` is preserved. The refresh token never leaves the httpOnly cookie; tabs share only the fact that a refresh finished and the new in-memory access token.

---

## ADR-007: Medical answers never leave Onboarding

## Status: Accepted

**Context.** The questionnaire includes medical conditions, medications, retinoids, allergies and skin conditions ([QS] Q8–Q12). `FR-008`(f) forbids mentioning them in cosmetic commentary, and requirements Q1 decided they are never sent to OpenAI (FR8.6). Two components build AI requests: ReportWriting (through the pipeline) and BeautyAssistant.

**Decision.** Onboarding is the only owner of answers. Other components can read answers only through a query that returns each answer with its question text and excludes every medical-flagged answer, including follow-ups, which inherit the flag. There is no query that returns medical answers outside Onboarding.

**Consequences.**
- *Positive:*
  - The privacy rule is enforced structurally, in one place, rather than in each prompt.
  - It is testable with canary strings (AC7.4.1).
- *Negative:* if a future feature legitimately needs medical answers (for example a clinician view), it needs a new, explicitly reviewed query.

**Alternatives rejected.** *Each AI component filters answers itself* — the filter would be duplicated, and a missed filter leaks health data to a third party.

**Security and compliance.** This is data minimisation for special-category health data (possible GDPR Art. 9 exposure; jurisdiction is still open with the client). Consent (FR4.1) is recorded in the same component.

---

## ADR-008: Frontend organised as feature folders mirroring the backend

## Status: Accepted

**Context.** The client's own team will extend the code with AI-assisted tools (`BC-005`, `NFR-011`). The auth layering is mandated (§5.3), and the team enforces layering with lint rules (practices, Q8).

**Decision.** Next.js feature folders mirror the backend components: auth, onboarding, photos, payment, analysis, report, visuals, chat, settings, journey. There is also a shared UI kit (shadcn/ui) and exactly one auth store and API client (WebAuthClient). UI code may not import auth internals (Q5 = A).

**Consequences.**
- *Positive:* a change to one backend area maps to one frontend folder, and lint rules can express the boundaries.
- *Negative:* some screens (Home) read from several features, so the rule is to compose them through their public exports only.

**Alternatives rejected.** *Route-only organisation* — this scatters feature logic across pages and makes the layering rule hard to lint.

**Security and compliance.** Token handling is confined to one module (FE-003, FE-007), which reduces the XSS blast radius described in `ASM-001`.

---

## ADR-009: One private MediaStore for every face image and PDF

## Status: Accepted

**Context.** Face photos, 24 generated images and the PDF are the most sensitive data the platform holds. Hosting and storage are undecided (`NFR-010`), and retakes must replace files, not orphan them (`BR-005`).

**Decision.** MediaStore owns `StoredFile` and every read and write of binary media, through a storage adapter. Files are served only through an owner-checked endpoint, never from public paths. Photos are re-encoded on write to strip metadata, and HEIC is converted.

**Consequences.**
- *Positive:*
  - One privacy boundary to test.
  - One place to add encryption and signed URLs when hosting is chosen.
  - Changing the storage backend doesn't touch other components.
- *Negative:* every image load goes through the backend (or a signed URL later) instead of a public CDN path; caching is decided in the NFR stages.

**Alternatives rejected.** *Each component writes files where it likes* — this creates several privacy boundaries, orphaned files, and host-specific code in many places.

**Security and compliance.** Ownership checks return 404 to other users (AC1.8.1). Metadata stripping removes location data (US5.8). Encryption at rest is decided with hosting.

---

## ADR-010: Report text and the published report are separate owners

## Status: Accepted

**Context.** AI-written text changes with prompts and models. The published report changes with design, templates and the PDF ([RD], [RT]). Reports auto-publish with no human review (`BR-002`), so text must be validated before it becomes part of a report.

**Decision.** ReportWriting owns `ReportText`, which it validates against a schema, with retries. Report owns `Report` (publish state, template version, cached PDF) and reads the text, measurements and images to build its views.

**Consequences.**
- *Positive:*
  - A prompt change never touches layout code.
  - Validation happens before publishing.
  - A regenerated image invalidates only the PDF cache, not the text.
- *Negative:* two records to join when reading a report. This is simple within one database.

**Alternatives rejected.** *Report generates its own text* — this mixes AI vendor handling with template and PDF logic and makes validation-before-publish harder to guarantee.

**Security and compliance.** Text validation includes "no raw field names" and "no medical claims" ([RT] §13–§15), which reduces the risk of publishing unsafe AI output without review (`CON-006`).
