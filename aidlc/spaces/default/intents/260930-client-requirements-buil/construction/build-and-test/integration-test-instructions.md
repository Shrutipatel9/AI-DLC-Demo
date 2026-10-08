# Integration Test Instructions

## Setup
Real PostgreSQL (`app_test`, `app_e2e` databases, migrations applied — never SQLite), Mailpit, the real background worker, and fakes for OpenAI and Stripe (`scripts/ci-env.sh`).

## Run
- Backend API + database integration (all modules): `cd backend && source ../scripts/ci-env.sh && uv run pytest -m "not perf" --cov=app --cov-fail-under=80`.
- Cross-unit browser journeys: `bash scripts/verify.sh` runs Playwright (phone 360 px + desktop; `journey.spec.ts` also on WebKit and Firefox) through sign-up → onboarding → photos → payment → analysis → visuals → Home → report/PDF → chat, plus session, settings and failure cases, with axe on every main screen.

## Key boundaries covered
Identity ↔ every protected route; onboarding public port → AI request (no medical answers); photos identity check → checkout and analysis start; Stripe webhook → payment state (never starts analysis); worker ↔ jobs queue; images → analysis slots; report ↔ paywall; journey rule ↔ every module's public port.

## Coverage targets
≥ 80% line coverage per app (enforced); every FR/AUTH/BR/FE client ID mapped (`scripts/check-requirement-map.py`).
