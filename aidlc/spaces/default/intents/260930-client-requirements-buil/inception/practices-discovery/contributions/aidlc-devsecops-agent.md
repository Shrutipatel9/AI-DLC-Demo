**Collaborator:** aidlc-devsecops-agent

## Contribution

Security-engineering review of the lead draft (`team-practices.md`, `discovered-rules.md`, `evidence.md`). The project is greenfield: there is no code, no CI and no security tooling, so everything tagged **[Suggested — confirm]** below is a delivery-team proposal for the interview. It is not a team fact. Client-stated items cite their requirement IDs from `client_requirements.md`.

### 1. Why this project needs security practices in the team rules

The platform handles data that is more sensitive than a typical web app. That is why security controls belong in the affirmed practices from the first Bolt, not added later:

| Data | Where it comes from | Proposed sensitivity tier [Recommendation] |
|---|---|---|
| Facial photos (3 angles), AI-generated derivatives (24 images per report), landmark-distance "identity signature" | `FR-005`, `FR-006`, `FR-020`, `FR-022`, `ASM-010`, `DATA-005`, `DATA-009`, `DATA-010` | **Restricted.** Face images plus a derived identity signature can count as biometric data in several jurisdictions. |
| Questionnaire answers on medical conditions, medications, allergies and appearance-related distress | `FR-003`, `FR-004`, `DATA-004` | **Restricted.** Health data. |
| Password hashes, OTP hashes, refresh-token identifiers, `reset_token`, JWT signing key | `AUTH-010`–`AUTH-015`, `DATA-001`–`DATA-003` | **Restricted.** Credentials. |
| Email, full name, Stripe payment identifiers, chat transcripts | `FR-002`, `DATA-008`, `DATA-011` | **Confidential.** PII. |

Two facts make this more urgent:
- Reports auto-publish with no human review (`BR-002`, `CON-006`), so no one looks at data or output before users do.
- A formal data-retention/privacy policy is explicitly out of scope (§2.2).

The consequence is that engineering practices are the only safeguard for this data in the current scope. The target jurisdiction, and so whether GDPR Art. 9 or US state biometric laws (for example BIPA) apply, is not stated anywhere. This is an open item for the compliance lead. It is not something this stage should decide (see §8).

### 2. Code Style: lint rules with security value [Suggested — confirm]

These add to the lead's Ruff / ESLint / Prettier suggestion. They do not replace it. Each one is a linter configuration, so it satisfies `org.md` § Code Style ("defer to project linter config").

**Backend (`backend/pyproject.toml`)**
- Enable Ruff's `S` rule family (flake8-bandit port) alongside the defaults, plus `B` (bugbear). This catches hardcoded passwords/keys (`S105`–`S107`), `assert` used for auth checks (`S101`, allowed only under `tests/`), unsafe `pickle`/`yaml.load`, `subprocess` with `shell=True`, weak hashes/ciphers, disabled TLS verification (`S501`) and missing request timeouts (`S113`).
- Per-file ignore of `S101` for `tests/**` only. Every other suppression is an inline `# noqa: S###` with a one-line justification. No blanket ignores.
- A separate Bandit run adds little once Ruff `S` is enabled. **Recommend Ruff `S` only**, to keep one tool.

**Frontend (ESLint config at the frontend root)**
- `eslint-plugin-security` and `eslint-plugin-no-unsanitized`, plus `react/no-danger` as an **error**. Any use of `dangerouslySetInnerHTML` must be explicitly suppressed with a justification.
- Reason: `ASM-001` accepts that XSS remains a risk to the in-memory access token and says to mitigate it with output encoding and dependency hygiene. Raw HTML injection is the main way XSS gets into a React app. This matters most for the AI Beauty Assistant chat (`FR-019`) and the AI narratives (`FR-008`), which render model-generated text. That text must be treated as untrusted and rendered as text or through a sanitizing Markdown renderer.
- `"strict": true` in `tsconfig.json` (already in the lead draft). AGREE.

### 3. Secret handling

**3a. A `.gitignore` gap to fix before the first commit (evidence finding).** The current `.gitignore` is only the AI-DLC block plus Node/editor entries. It does **not** ignore:
- `.env` or `.env.*`. `*.local` covers `.env.local` only, not `.env`, `.env.development` or `.env.production`.
- `*.pem`, `*.key`
- Python artefacts: `__pycache__/`, `.venv/`, `*.pyc`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `.mypy_cache/`, `.ruff_cache/`
- `.next/` (Next.js build output)
- Any local upload/media directory where development photos might land, for example `backend/uploads/` or `backend/media/`

Because `backend/` does not exist yet, the first backend Bolt could commit a `.env` holding OpenAI, Stripe and JWT secrets. Suggested addition, with `!` negations so the examples stay tracked:
```
.env
.env.*
!.env.example
!**/.env.example
*.pem
*.key
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.coverage
htmlcov/
.mypy_cache/
.ruff_cache/
.next/
coverage/
backend/uploads/
backend/media/
```
(The exact upload path depends on the storage decision in §6.)

**3b. Configuration pattern [Suggested — confirm].**
- Backend: one typed settings object (for example `pydantic-settings`) loaded from environment variables.
- The app **fails fast at startup** if a required secret is missing, empty, or a known placeholder value.
- Commit `.env.example` for each app with placeholder values only.
- Secrets in scope include more than the OpenAI key `NFR-008` names: the JWT signing key, the Stripe secret key, the Stripe webhook signing secret, email/OTP provider credentials, and the database URL.
- JWT signing key: at least 256 bits of randomness if HS256 is used. The algorithm is pinned server-side, and tokens with `alg: none` or an unexpected algorithm are rejected.
- Frontend: only values prefixed `NEXT_PUBLIC_` reach the browser. Anything with that prefix must be non-secret, such as the API base URL.

**3c. Secret scanning [Suggested — confirm].**
- A `pre-commit` hook running **Gitleaks** on every developer machine. It blocks the commit locally, which is the only enforcement point available while no CI exists.
- If the repository is on GitHub (the remote is `github.com/Shrutipatel9/AI-DLC-Demo`), enable **secret scanning and push protection** as a backstop. Availability depends on whether the repo is public or private and on the GitHub plan. This is an interview question.
- If a secret is ever committed: revoke and rotate it first, then clean the history. Deleting the file alone is never enough.

### 4. Dependency and supply-chain controls [Suggested — confirm]

| Control | Backend | Frontend |
|---|---|---|
| Lockfile committed and used for installs | `uv.lock` (uv) or `requirements*.txt` compiled with `pip-compile --generate-hashes`; install from the lock only | `package-lock.json` (or `pnpm-lock.yaml`); install with `npm ci`, never `npm install`, in scripted runs |
| Version pinning | Exact pins via the lockfile; ranges only in the manifest | Same |
| Known-vulnerability scan | `pip-audit` against the lock | `npm audit --audit-level=high` |
| Gate threshold | Fail on **High/Critical** with a fix available; Medium is a warning tracked as a backlog item | Same |
| Automated updates | Dependabot (GitHub native) for `pip`/`uv`, `npm` and, if CI is added, `github-actions`; weekly | Same |
| Accepted-risk waivers | Recorded in the repo (for example `.pip-audit-ignore` / audit-ignore entries) with a reason and an expiry date | Same |

Stack-specific notes:
- Use `opencv-python-headless`, not `opencv-python`, on the server. It avoids the GUI/X11 dependency surface and is the correct wheel for a headless API.
- Pin the `mediapipe` model file (Face Landmarker `.task`) and verify it by checksum. Do not download it at runtime from an unpinned URL.
- **Next.js:** keep it on a patched release line. Never treat Next.js middleware as the authorization boundary: CVE-2025-29927 allowed middleware to be bypassed with a crafted header. The architecture is already correct, because `AUTH-005`/`AUTH-007` put authorization in the FastAPI backend. Middleware may redirect for user experience only.
- An SBOM (Syft or `cyclonedx-py` / `@cyclonedx/cyclonedx-npm`) is **optional** in this scope. It is useful at client handoff (`NFR-011`) but not a gate.

### 5. SAST / DAST [Suggested — confirm]

- **SAST:** Ruff `S` and the ESLint security plugins above are the baseline and run in the same pre-merge step as the linters. Add **Semgrep** with the community Python and TypeScript/React rulesets as a second layer, blocking on High. If GitHub Actions is adopted and the repo is eligible, **CodeQL** is an acceptable alternative to Semgrep. Choose one, not both.
- **DAST:** there is no deployed environment (`NFR-010`, `CON-007`) and the Operation stages are skipped, so **no DAST gate is proposed for this workflow**. Optional: run an OWASP ZAP **baseline** (passive) scan against a local run of both apps once Construction produces them, as a one-off check. Record its findings, but do not use it as a merge gate.
- **Dependency and secret scanning** are covered in §3–§4.
- **IaC scanning:** not applicable. There is no infrastructure-as-code while hosting is undecided. Revisit when a host is chosen.

### 6. Sensitive data in logs, tests, uploads and third-party calls

**Logging [Suggested — confirm; candidate rules in §9]**
- Never log any of these:
  - photo bytes or base64 image payloads
  - questionnaire answers (especially medical/medication/allergy answers)
  - chat message content
  - OTP codes, passwords, access/refresh tokens, `reset_token`
  - the `Authorization` header or the `Cookie` header
  - full Stripe webhook bodies
  - OpenAI request or response payloads
- Log the internal user ID and a request/correlation ID instead. Mask email addresses if they are logged at all.
- Implement this as one central redaction filter in the logging setup, not as per-call discipline.
- FastAPI validation errors (422) echo the request body by default. Make sure the error handler does not return or log password/OTP fields.
- The auth flows need security-event logging, without the secrets themselves: login success/failure, OTP failure, lockout (`AUTH-011`), refresh-token reuse detection and family revocation (`AUTH-012`), password reset/change (`AUTH-015`, `AUTH-016`), 402/409 gate rejections (`FR-015`, `BR-005`). Without these logs, `AUTH-012` reuse detection cannot be investigated.

**Tests [Suggested — confirm]**
- Test fixtures use **synthetic or properly licensed face images only**. Never use real client or end-user photos, and never commit photos of team members without consent.
- Questionnaire fixtures use obviously fake answers.
- No production data in tests.
- This works with the lead's candidate rule that tests never call paid third-party APIs. AGREE with that candidate, and extend it: faked OpenAI and image-generation clients must also mean that no photos leave the machine during tests.
- The security-critical negative paths below need explicit tests. The client's Section 12 Testing row already requires every `AUTH-*` and `BR-*` to map to at least one test:

| Negative test | Requirement |
|---|---|
| Refresh-token reuse revokes the whole token family | `AUTH-012` |
| OTP lockout after 5 failures; OTP expiry | `AUTH-011` |
| CSRF: refresh/logout rejected without `X-Requested-With` or from a disallowed Origin | `AUTH-013` |
| `reset_token` rejected on reuse, on expiry, and when presented as a Bearer token | `AUTH-015` |
| Analysis and report endpoints return 402 before payment | `FR-015`, `BR-001` |
| Checkout and analysis start return 409 on an identity-inconsistent photo set | `BR-005` step 8 |
| A Stripe webhook with an invalid signature is rejected | `FR-015`; see note below |
| **Object-level authorization:** user A cannot read user B's photos, report, PDF, AI visuals or chat | `AUTH-007`, `AUTH-008`. There is only one role (`AUTH-009`), so per-object ownership checks are the main authorization control. |

**Uploads (`FR-005`, `FR-006`) [Suggested — confirm]**
- Enforce a maximum upload size at the API.
- Check the file type from its content (magic bytes), not only the `Content-Type` header.
- Cap decoded pixel dimensions to prevent decompression bombs.
- Re-encode the image server-side, which also **strips EXIF metadata**. Camera-captured phone photos often carry GPS coordinates.
- Store under server-generated names. Never use the client filename in a path.

**Storage (open item).** The draft does not yet say where photos, generated images and PDFs are stored: database, local disk or object storage. With hosting undecided, recommend a storage abstraction selected by configuration, following the same pattern `NFR-013` requires for image generation, so the storage backend can change without code changes. Regardless of where files are stored:
- They are served only through authenticated, ownership-checked backend endpoints, or short-lived signed URLs.
- They never have public, guessable URLs.
- Encryption at rest is required when the host is chosen.

**Stripe webhook [Candidate — see §9].** The webhook updates payment status (`FR-015`) and that status unlocks analysis (`BR-001`). A forged webhook would therefore give away paid reports. The handler must:
- verify the `Stripe-Signature` header with the webhook signing secret on the raw request body,
- be idempotent on the event ID,
- never trust amount or currency from the client redirect.

**Third-party data flows (surface, do not resolve).** `FR-008` sends photos and questionnaire answers to OpenAI as model context, and `FR-008`(f) forbids the narrative from *referencing* medical answers. From a data-minimisation standpoint, the safer design is to **leave medical, medication and allergy answers out of the OpenAI payload altogether**, while still sending the distress-related answers `FR-008`(e) needs. This may conflict with `FR-008`'s "uses the questionnaire answers as context". Per the client document's rule to surface conflicts rather than resolve them, it goes to the interview or to requirements analysis, not into a rule here.

The client should also confirm that sending facial photos to OpenAI, and to any swapped-in vendor under `NFR-013`, is acceptable under their privacy position, including the vendor's data-retention and training-use settings.

### 7. Security gates without a CI pipeline

The lead correctly flags that `classic` requires CI before merge, yet the CI Pipeline stage is skipped. The security gates depend on how that tension is resolved:

| Gate | Where it runs if there is no CI (local) | Where it runs if a minimal GitHub Actions workflow is affirmed | Blocks on |
|---|---|---|---|
| Secret scan (Gitleaks) | `pre-commit` hook | Also in the workflow | Any finding |
| Lint including security rules (Ruff `S`, ESLint security plugins) | Pre-merge script run before the Bolt gate | Workflow job on every PR | Any error |
| SAST (Semgrep or CodeQL) | Pre-merge script | Workflow job | High/Critical |
| Dependency audit (`pip-audit`, `npm audit`) | Pre-merge script | Workflow job, plus Dependabot alerts | High/Critical with a fix available |
| Security negative tests (§6) | Part of the normal test run | Part of the normal test run | Any failure |

**Recommendation:** a single script per app (for example `make check` / `npm run check`) that runs lint, tests, SAST and the dependency audit. The Bolt gate records that the script passed. If a GitHub Actions workflow is later affirmed, it runs the same command, so the local and CI gates cannot drift apart.

### 8. Gaps the interview must resolve (security)

1. **`.gitignore` hardening** (§3a): approve adding the listed entries before the first commit?
2. **Secret-scanning enforcement point:** Gitleaks pre-commit only, or also GitHub push protection? Is the repo public or private, and on what GitHub plan?
3. **Security tooling set:** Ruff `S` + ESLint security plugins + (Semgrep **or** CodeQL) + `pip-audit` / `npm audit` + Dependabot. Affirm, trim or replace.
4. **Vulnerability gate threshold:** block on High/Critical (proposed), or Critical only?
5. **Python dependency manager and lockfile format:** uv (`uv.lock`), or pip-tools with hashes?
6. **Where security gates run:** tied to the CI-before-merge decision the lead already raised (§7).
7. **Photo and generated-asset storage location and access pattern** (§6): a decision for the architect, but the practice "no public URLs; ownership-checked access only" can be affirmed now.
8. **Jurisdiction / regulatory regime** for biometric and health data: which user markets are targeted? Route to compliance. It affects encryption, consent and deletion obligations, even though a formal retention policy is out of scope (§2.2).
9. **Medical answers in the OpenAI payload** (§6): exclude them (data minimisation), or send them per the literal `FR-008` wording? Surface to the client.
10. **Test-image sourcing:** confirm synthetic/licensed faces only for fixtures.

### 9. Candidate rules for `discovered-rules.md` (not mandated; confirm or drop in the interview)

- Candidate: NEVER commit `.env` files, private keys, or real secrets of any kind; commit `.env.example` files with placeholders only, and keep `.gitignore` covering them. *(Already binding for code through the `construction.md` § Security guardrail "Never hardcode credentials"; see Positions.)*
- Candidate: ALWAYS load every secret (JWT signing key, Stripe secret and webhook secret, OpenAI key, email provider credentials, database URL) from environment/configuration, and fail fast at startup when one is missing.
- Candidate: NEVER log photo data, questionnaire answers, chat content, OTPs, passwords, tokens, `reset_token`, or auth/cookie headers.
- Candidate: ALWAYS verify the Stripe webhook signature on the raw request body and process each event ID idempotently before changing payment status.
- Candidate: ALWAYS enforce object-level ownership checks on every endpoint that returns a user's photos, report, PDF, generated images or chat.
- Candidate: NEVER serve photos, generated images or report PDFs from public or guessable URLs.
- Candidate: ALWAYS strip EXIF metadata and re-encode uploaded images server-side, with size and pixel-dimension limits.
- Candidate: NEVER use real user or client photos in tests or fixtures; use synthetic or licensed images only.
- Candidate: NEVER render AI-generated text (narratives, chat) as raw HTML in the frontend; `dangerouslySetInnerHTML` is disallowed unless the output is sanitized and the suppression is justified.
- Candidate: ALWAYS install dependencies from a committed lockfile, and block merge on High/Critical known vulnerabilities that have an available fix unless a dated waiver is recorded.

## Positions

- AGREE: The `FE-002` / `ASM-001` token-storage rules (refresh token in an httpOnly cookie only; no `localStorage`/`sessionStorage`/Zustand `persist`) as Mandated/Forbidden. They are client-stated and are the primary XSS blast-radius control.
- AGREE: Server-side enforcement of payment (`FR-015`, `BR-001`) and of the identity re-check at checkout and analysis start (`BR-005` step 8) as Mandated. Client-side gates alone would be bypassable.
- AGREE: Config-driven, host-neutral handling of environment values (`NFR-008`, `NFR-010`). It is also the secret-management foundation.
- AGREE: The lead surfaces the CI-before-merge tension instead of silently resolving it. Every security gate in §7 depends on that decision.
- AGREE: The candidate that automated tests never call paid third-party APIs. It also prevents facial photos from leaving the machine during tests.
- OBJECT: The candidate "NEVER commit secrets, API keys or `.env` files" is listed only as a candidate. It restates the active `construction.md` § Security guardrail ("Never hardcode credentials, API keys, or secrets"), so it is already binding in Construction and should be presented as such, not as optional.
- OBJECT: The Mandated config rule covers only the OpenAI key/base URL/model and pricing. It should be widened to every secret (JWT signing key, Stripe secret and webhook secret, email provider credentials, database URL), or a companion candidate added, so nothing implies other secrets may be hardcoded.
- OBJECT: `evidence.md` does not record that the current `.gitignore` lacks `.env`, key-file, Python-cache and `.next/` entries. This is a concrete finding that must be fixed before the first commit, and it belongs under tensions/open items.
- OBJECT: The Code Style section lists Ruff and ESLint with no security rule sets. Adding Ruff `S` and the ESLint security / no-unsanitized plugins costs nothing, and it is the mitigation `ASM-001` itself calls for.
- OBJECT: There is no practice for Stripe webhook signature verification, sensitive-data logging, test-image sourcing or object-level authorization. For a product that stores facial photos and health answers and auto-publishes with no review (`CON-006`), these belong at least as interview candidates.
