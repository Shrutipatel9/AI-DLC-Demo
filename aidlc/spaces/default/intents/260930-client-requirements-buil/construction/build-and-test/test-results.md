# Test Results — Build and Test

Run: `bash scripts/verify.sh` (full gate, same order as CI) on 2026-10-08, Windows 11 + Docker Desktop. **Exit 0 — "All checks passed."** Elapsed 1146 s. Log: `.verify/verify-full.log` (local, git-ignored).

## Build
- Backend: `uv sync --frozen`, Ruff lint + format, `mypy --strict app`, import-linter **36 contracts kept, 0 broken** — success.
- Frontend: `pnpm install --frozen-lockfile`, ESLint, Prettier, `tsc --noEmit`, `pnpm build` — success. OpenAPI types up to date (no drift).

## Tests
| Suite | Total | Passed | Failed | Skipped | Coverage |
|---|---|---|---|---|---|
| Backend pytest (all modules, real PostgreSQL) | 943 | 938 | 0 | 5 (opt-in `eval`) | **98.32%** lines (floor 80%) |
| Backend latency (p95) | 11 | 11 | 0 | 0 | — |
| Frontend Vitest + RTL (46 files) | 363 | 363 | 0 | 0 | **96.9%** lines (floor 80%) |
| Playwright E2E (Chromium phone 360 px + desktop for all specs; WebKit + Firefox phone + desktop for `journey.spec.ts`; axe) | 50 | 50 | 0 | 0 | — |
| Requirement-to-test map | 57 IDs | OK | 0 | — | — |

Per-unit commands from every `unit-test-instructions.md` are subsets of these runs (each suite ran once; no double counting).

## Latency (p95, all within target)
register 79.1 ms (≤ 500) · login 80.9 (≤ 500) · verify 26.4 (≤ 500) · me 9.5 (≤ 100) · health 2.6 (≤ 50) · refresh 19.4 (≤ 200) · logout 14.1 (≤ 200) · resend-code 12.8 (≤ 200) · password forgot 24.9 / verify-code 27.8 / reset 66.0 / change 119.9 (≤ 500). Forgot-password enumeration timing: median spread ≈ 2.4 ms, p95 spread ≈ 2.8 ms (< 50 ms).

## Bundle budget
All 20 routes ≤ 200 KB gzipped JS; largest `/settings/password` 197.1 KB.

## Security
Gitleaks: no leaks · `pip-audit`: no known vulnerabilities · `pnpm audit --prod`: none (high+) · auth deny-list OK · app independence OK.

## In-stage fixes made during this run (rung 1, build scripts/config only)
1. `scripts/verify.sh` and CI: the backend test list had a stray literal `\n` and lacked `tests/journey`, `tests/settings`, `tests/traceability`, `tests/chat` — fixed.
2. `scripts/verify.sh`: requirement-map step passed a Git-Bash path to native Python — now repo-relative like CI.
3. Gitleaks working-tree scan flagged a developer's git-ignored `backend/.env` (never committed) and a false positive in `tests/identity/test_sessions.py`; added `.env`/`.env.local` to the documented allow-list of git-ignored local files and removed the false-positive variable.
4. `scripts/verify.sh` and CI did not run `journey.spec.ts`/`settings.spec.ts` or WebKit/Firefox — now they do (the 50 E2E results above include them).

No quality target was lowered.
