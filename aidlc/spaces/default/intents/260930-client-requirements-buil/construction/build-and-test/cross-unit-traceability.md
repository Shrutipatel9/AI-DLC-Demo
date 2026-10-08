# Cross-Unit Traceability

## Verdict

**PASS** — 409 IDs (every FR/NFR in `requirements.md` and every AC in `stories.md`): 404 covered by an existing implementation or test file, 5 N/A or Deferred with a reason, 0 uncovered.

Sources: every `construction/*/code-generation/traceability.json`, story `Traces:` lines (a requirement is covered when an AC of a story tracing it is covered), `docs/requirement-test-map.json` for client IDs, and parent FR groups covered when all their sub-requirements are.

## Deferred and N/A (surfaced at the gate)

- **NFR-010** — N/A — no host assumed or built (client-confirmed); nothing to test
- **AC1.3.2** — Deferred — branch protection is a GitHub repository setting an admin applies after push (docs/branch-protection.md); the required CI jobs exist
- **AC7.2.6** — Deferred — opt-in (eval): timed run on the real vendors before handover
- **AC7.9.4** — Deferred — opt-in (eval): real-model narrative check before handover
- **AC9.1.4** — Deferred — manual resemblance check on the real image vendor before handover (ASM-011)

## Per-ID coverage

| ID | Status | Owning unit | Target |
|---|---|---|---|
| AC1.1.1 | OK | u1-walking-skeleton | `README.md` |
| AC1.1.2 | OK | u1-walking-skeleton | `scripts/check-app-independence.sh` |
| AC1.1.3 | OK | u1-walking-skeleton | `.gitignore` |
| AC1.10.1 | OK | u4-photos | `backend/tests/media/test_storage.py` |
| AC1.10.2 | OK | u4-photos | `backend/tests/media/test_media_store.py` |
| AC1.10.3 | OK | u4-photos | `backend/tests/media/test_media_store.py` |
| AC1.11.1 | OK | u4-photos | `backend/tests/face/test_face_geometry.py` |
| AC1.11.2 | OK | u4-photos | `backend/tests/face/test_face_geometry.py` |
| AC1.11.3 | OK | u4-photos | `backend/tests/face/test_face_geometry.py` |
| AC1.12.1 | OK | u6-analysis-core | `backend/tests/ai/test_fakes_and_selection.py` |
| AC1.12.2 | OK | u6-analysis-core | `backend/tests/ai/test_openai_adapters.py` |
| AC1.12.3 | OK | u6-analysis-core | `backend/tests/ai/test_fakes_and_selection.py` |
| AC1.13.1 | OK | u10-journey-settings | `backend/tests/traceability/test_requirement_map.py` |
| AC1.13.2 | OK | u10-journey-settings | `frontend/e2e/journey.spec.ts` |
| AC1.13.3 | OK | u10-journey-settings | `frontend/e2e/journey.spec.ts` |
| AC1.2.1 | OK | u1-walking-skeleton | `docker-compose.yml` |
| AC1.2.2 | OK | u1-walking-skeleton | `backend/alembic/versions/0001_u1_identity.py` |
| AC1.2.3 | OK | u1-walking-skeleton | `backend/pyproject.toml` |
| AC1.2.4 | OK | u1-walking-skeleton | `backend/alembic/versions/0001_u1_identity.py` |
| AC1.3.1 | OK | u1-walking-skeleton | `.github/workflows/ci.yml` |
| AC1.3.2 | Deferred | — | branch protection is a GitHub repository setting an admin applies after push (docs/branch-protection.md); the required CI jobs exist |
| AC1.3.3 | OK | u1-walking-skeleton | `backend/pyproject.toml` |
| AC1.3.4 | OK | u1-walking-skeleton | `frontend/eslint.config.mjs` |
| AC1.3.5 | OK | u1-walking-skeleton | `backend/pyproject.toml` |
| AC1.4.1 | OK | u1-walking-skeleton | `.pre-commit-config.yaml` |
| AC1.4.2 | OK | u1-walking-skeleton | `backend/pyproject.toml` |
| AC1.4.3 | OK | u1-walking-skeleton | `.github/dependabot.yml` |
| AC1.4.4 | OK | u1-walking-skeleton | `scripts/check-denylist.sh` |
| AC1.5.1 | OK | u1-walking-skeleton | `backend/app/platform/settings.py` |
| AC1.5.2 | OK | u1-walking-skeleton | `backend/tests/platform/test_settings.py` |
| AC1.5.3 | OK | u1-walking-skeleton | `backend/tests/platform/test_settings.py` |
| AC1.5.4 | OK | u1-walking-skeleton | `scripts/verify.sh` |
| AC1.6.1 | OK | u1-walking-skeleton | `backend/app/platform/email/__init__.py` |
| AC1.6.2 | OK | u1-walking-skeleton | `backend/app/platform/email/smtp.py` |
| AC1.6.3 | OK | u1-walking-skeleton | `backend/app/platform/email/fake.py` |
| AC1.6.4 | OK | u1-walking-skeleton | `frontend/e2e/skeleton.spec.ts` |
| AC1.7.1 | OK | u6-analysis-core | `backend/tests/jobs/test_queue.py` |
| AC1.7.2 | OK | u6-analysis-core | `backend/tests/jobs/test_worker.py` |
| AC1.7.3 | OK | u6-analysis-core | `backend/tests/jobs/test_worker.py` |
| AC1.8.1 | OK | u1-walking-skeleton | `backend/app/identity/dependencies.py` |
| AC1.8.2 | OK | u1-walking-skeleton | `backend/app/platform/middleware.py` |
| AC1.8.3 | OK | u1-walking-skeleton | `backend/app/platform/logging.py` |
| AC1.9.1 | OK | u1-walking-skeleton | `frontend/src/lib/auth/store.ts` |
| AC1.9.2 | OK | u1-walking-skeleton | `frontend/src/lib/api/client.ts` |
| AC1.9.3 | OK | u1-walking-skeleton | `frontend/src/lib/auth/hooks.ts` |
| AC10.1.1 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_api.py` |
| AC10.1.2 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_api.py` |
| AC10.1.3 | OK | u9-beauty-assistant | `frontend/src/components/chat/chat-screen.test.tsx` |
| AC10.1.4 | OK | u9-beauty-assistant | `frontend/src/components/chat/chat-screen.test.tsx` |
| AC10.1.5 | OK | u9-beauty-assistant | `frontend/src/components/chat/chat-screen.test.tsx` |
| AC10.1.6 | OK | u9-beauty-assistant | `frontend/e2e/chat.spec.ts` |
| AC10.1.7 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_eval.py` |
| AC10.2.1 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_api.py` |
| AC10.2.2 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_eval.py` |
| AC10.3.1 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_api.py` |
| AC10.3.2 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_api.py` |
| AC10.3.3 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_limit_race.py` |
| AC10.3.4 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_api.py` |
| AC11.1.1 | OK | u8-report-home | `frontend/src/components/home/home-overview.test.tsx` |
| AC11.1.2 | OK | u8-report-home | `frontend/src/components/home/home-overview.test.tsx` |
| AC11.1.3 | OK | u8-report-home | `frontend/src/components/home/home-overview.test.tsx` |
| AC11.1.4 | OK | u8-report-home | `frontend/src/components/home/home-overview.test.tsx` |
| AC11.2.1 | OK | u8-report-home | `frontend/src/components/app/app-header.test.tsx` |
| AC11.2.2 | OK | u8-report-home | `frontend/src/components/app/app-header.test.tsx` |
| AC11.3.1 | OK | u8-report-home | `frontend/src/components/home/home-overview.test.tsx` |
| AC11.4.1 | OK | u10-journey-settings | `backend/tests/settings/test_settings_api.py` |
| AC11.4.2 | OK | u10-journey-settings | `frontend/src/components/settings/settings-tabs.test.tsx` |
| AC11.5.1 | OK | u2-session-security | `backend/app/identity/password_change.py` |
| AC11.5.2 | OK | u2-session-security | `frontend/src/components/settings/change-password-form.tsx` |
| AC11.5.3 | OK | u2-session-security | `backend/app/identity/password_change.py` |
| AC11.6.1 | OK | u10-journey-settings | `backend/tests/settings/test_settings_api.py` |
| AC11.6.2 | OK | u10-journey-settings | `frontend/src/components/settings/settings-tabs.test.tsx` |
| AC11.7.1 | OK | u2-session-security | `frontend/src/components/feedback/toast.tsx` |
| AC11.7.2 | OK | u2-session-security | `frontend/src/components/feedback/toast.tsx` |
| AC11.7.3 | OK | u2-session-security | `frontend/src/components/feedback/confirm-dialog.tsx` |
| AC11.7.4 | OK | u2-session-security | `frontend/src/components/ui/form-field.tsx` |
| AC11.7.5 | OK | u2-session-security | `frontend/src/components/ui/toaster.tsx` |
| AC11.8.1 | OK | u10-journey-settings | `backend/tests/journey/test_next_step.py` |
| AC11.8.2 | OK | u10-journey-settings | `frontend/src/components/app/protected-route.test.tsx` |
| AC2.1.1 | OK | u10-journey-settings | `frontend/src/components/landing/landing-page.test.tsx` |
| AC2.1.2 | OK | u10-journey-settings | `frontend/src/components/landing/landing-page.test.tsx` |
| AC2.1.3 | OK | u10-journey-settings | `frontend/src/components/landing/landing-page.test.tsx` |
| AC2.2.1 | OK | u10-journey-settings | `frontend/src/components/landing/landing-page.test.tsx` |
| AC2.2.2 | OK | u10-journey-settings | `frontend/src/components/landing/landing-page.test.tsx` |
| AC3.1.1 | OK | u1-walking-skeleton | `backend/tests/identity/test_register_api.py` |
| AC3.1.2 | OK | u1-walking-skeleton | `backend/tests/identity/test_register_api.py` |
| AC3.1.3 | OK | u1-walking-skeleton | `backend/tests/identity/test_register_api.py` |
| AC3.1.4 | OK | u1-walking-skeleton | `backend/tests/identity/test_passwords.py` |
| AC3.1.5 | OK | u1-walking-skeleton | `backend/tests/identity/test_register_api.py` |
| AC3.10.1 | OK | u2-session-security | `frontend/src/lib/auth/refresh-coordinator.ts` |
| AC3.10.2 | OK | u2-session-security | `frontend/src/lib/auth/refresh-coordinator.ts` |
| AC3.10.3 | OK | u2-session-security | `frontend/src/lib/api/client.ts` |
| AC3.10.4 | OK | u2-session-security | `frontend/src/lib/auth/refresh-coordinator.ts` |
| AC3.10.5 | OK | u2-session-security | `frontend/src/lib/auth/refresh-coordinator.ts` |
| AC3.11.1 | OK | u2-session-security | `frontend/src/lib/auth/refresh-coordinator.ts` |
| AC3.2.1 | OK | u1-walking-skeleton | `backend/tests/identity/test_codes.py` |
| AC3.2.2 | OK | u1-walking-skeleton | `backend/tests/identity/test_codes.py` |
| AC3.2.3 | OK | u1-walking-skeleton | `backend/tests/identity/test_codes.py` |
| AC3.2.4 | OK | u1-walking-skeleton | `backend/tests/identity/test_codes.py` |
| AC3.2.5 | OK | u1-walking-skeleton | `backend/tests/identity/test_codes.py` |
| AC3.2.6 | OK | u1-walking-skeleton | `frontend/src/components/auth/verify-form.test.tsx` |
| AC3.3.1 | OK | u2-session-security | `frontend/src/components/auth/resend-code-button.tsx` |
| AC3.3.2 | OK | u2-session-security | `backend/app/identity/services.py` |
| AC3.3.3 | OK | u2-session-security | `backend/app/identity/services.py` |
| AC3.3.4 | OK | u2-session-security | `backend/app/identity/services.py` |
| AC3.4.1 | OK | u1-walking-skeleton | `backend/tests/identity/test_login_verify_api.py` |
| AC3.4.2 | OK | u1-walking-skeleton | `backend/tests/identity/test_login_verify_api.py` |
| AC3.4.3 | OK | u1-walking-skeleton | `backend/tests/identity/test_login_verify_api.py` |
| AC3.5.1 | OK | u2-session-security | `frontend/src/components/app/protected-route.tsx` |
| AC3.5.2 | OK | u2-session-security | `backend/app/identity/sessions.py` |
| AC3.5.3 | OK | u2-session-security | `backend/app/identity/sessions.py` |
| AC3.5.4 | OK | u2-session-security | `backend/app/identity/cookies.py` |
| AC3.5.5 | OK | u2-session-security | `frontend/src/lib/auth/store.ts` |
| AC3.6.1 | OK | u2-session-security | `backend/app/identity/sessions.py` |
| AC3.6.2 | OK | u2-session-security | `backend/app/platform/csrf.py` |
| AC3.6.3 | OK | u2-session-security | `backend/app/identity/sessions.py` |
| AC3.6.4 | OK | u2-session-security | `frontend/src/components/auth/security-notice.tsx` |
| AC3.7.1 | OK | u2-session-security | `frontend/src/components/app/user-menu.tsx` |
| AC3.7.2 | OK | u2-session-security | `backend/app/identity/sessions.py` |
| AC3.7.3 | OK | u2-session-security | `backend/app/identity/sessions.py` |
| AC3.7.4 | OK | u2-session-security | `frontend/src/lib/auth/session.ts` |
| AC3.8.1 | OK | u1-walking-skeleton | `backend/tests/identity/test_me_and_routes.py` |
| AC3.8.2 | OK | u1-walking-skeleton | `backend/tests/identity/test_me_and_routes.py` |
| AC3.9.1 | OK | u2-session-security | `backend/app/identity/password_reset.py` |
| AC3.9.2 | OK | u2-session-security | `backend/app/identity/password_reset.py` |
| AC3.9.3 | OK | u2-session-security | `backend/app/identity/password_reset.py` |
| AC3.9.4 | OK | u2-session-security | `backend/app/identity/password_reset.py` |
| AC3.9.5 | OK | u2-session-security | `backend/app/identity/password_reset.py` |
| AC4.1.1 | OK | u3-onboarding | `backend/app/onboarding/services.py` |
| AC4.1.2 | OK | u3-onboarding | `backend/app/onboarding/repositories.py` |
| AC4.1.3 | OK | u3-onboarding | `backend/app/onboarding/data/consent_v1.json` |
| AC4.2.1 | OK | u3-onboarding | `backend/app/onboarding/definition.py` |
| AC4.2.2 | OK | u3-onboarding | `backend/app/onboarding/definition.py` |
| AC4.2.3 | OK | u3-onboarding | `backend/app/onboarding/definition.py` |
| AC4.2.4 | OK | u3-onboarding | `backend/app/onboarding/definition.py` |
| AC4.2.5 | OK | u3-onboarding | `frontend/src/components/onboarding/questionnaire-wizard.tsx` |
| AC4.2.6 | OK | u3-onboarding | `backend/app/onboarding/routes.py` |
| AC4.2.7 | OK | u3-onboarding | `backend/app/onboarding/services.py` |
| AC4.3.1 | OK | u3-onboarding | `frontend/src/components/onboarding/questionnaire-wizard.tsx` |
| AC4.3.2 | OK | u10-journey-settings | `backend/tests/journey/test_next_step.py` |
| AC4.3.3 | OK | u3-onboarding | `backend/app/onboarding/services.py` |
| AC4.3.4 | OK | u3-onboarding | `frontend/src/components/onboarding/disclaimer-gate.tsx` |
| AC4.4.1 | OK | u3-onboarding | `backend/app/onboarding/data/questionnaire_v1.json` |
| AC4.4.2 | OK | u3-onboarding | `backend/app/onboarding/data/questionnaire_v1.json` |
| AC4.4.3 | OK | u3-onboarding | `backend/app/onboarding/data/questionnaire_v1.json` |
| AC4.4.4 | OK | u3-onboarding | `backend/app/onboarding/data/questionnaire_v1.json` |
| AC4.4.5 | OK | u3-onboarding | `backend/app/onboarding/data/questionnaire_v1.json` |
| AC5.1.1 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.1.2 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.10.1 | OK | u4-photos | `backend/tests/photos/test_checks.py` |
| AC5.10.2 | OK | u4-photos | `backend/tests/photos/test_checks.py` |
| AC5.11.1 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.11.2 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.11.3 | OK | u4-photos | `frontend/src/lib/photos/photos.test.ts` |
| AC5.11.4 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.11.5 | OK | u4-photos | `frontend/e2e/photos.spec.ts` |
| AC5.2.1 | OK | u4-photos | `backend/tests/photos/test_photos_config.py` |
| AC5.2.2 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.2.3 | OK | u4-photos | `backend/tests/photos/test_photos_api.py` |
| AC5.2.4 | OK | u4-photos | `backend/tests/photos/test_photos_api.py` |
| AC5.2.5 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.2.6 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.2.7 | OK | u4-photos | `backend/tests/media/test_media_store.py` |
| AC5.3.1 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.3.2 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.3.3 | OK | u4-photos | `frontend/src/components/photos/photo-flow.test.tsx` |
| AC5.3.4 | OK | u4-photos | `frontend/src/components/photos/camera-capture.tsx` |
| AC5.5.1 | OK | u4-photos | `backend/tests/photos/test_checks.py` |
| AC5.5.2 | OK | u4-photos | `backend/tests/photos/test_checks.py` |
| AC5.5.3 | OK | u4-photos | `backend/tests/photos/test_checks.py` |
| AC5.5.4 | OK | u4-photos | `frontend/src/components/photos/photo-thumbnail.test.tsx` |
| AC5.6.1 | OK | u4-photos | `backend/tests/photos/test_identity_decision.py` |
| AC5.6.2 | OK | u4-photos | `backend/tests/photos/test_identity_decision.py` |
| AC5.6.3 | OK | u4-photos | `backend/tests/photos/test_identity_decision.py` |
| AC5.6.4 | OK | u4-photos | `backend/tests/photos/test_identity_decision.py` |
| AC5.6.5 | OK | u4-photos | `backend/tests/photos/test_identity_service.py` |
| AC5.7.1 | OK | u10-journey-settings | `backend/tests/journey/test_next_step.py` |
| AC5.7.2 | OK | u10-journey-settings | `frontend/src/lib/journey/journey.test.tsx` |
| AC5.8.1 | OK | u4-photos | `backend/tests/media/test_images.py` |
| AC5.9.1 | OK | u4-photos | `backend/tests/photos/test_catalog_and_settings.py` |
| AC5.9.2 | OK | u4-photos | `backend/tests/photos/test_catalog_and_settings.py` |
| AC6.1.1 | OK | u5-payments | `frontend/src/components/payments/payment-screen.test.tsx` |
| AC6.1.2 | OK | u5-payments | `frontend/src/components/payments/payment-screen.test.tsx` |
| AC6.1.3 | OK | u5-payments | `backend/tests/payments/test_payments_api.py` |
| AC6.2.1 | OK | u5-payments | `backend/tests/payments/test_stripe_gateway.py` |
| AC6.2.2 | OK | u5-payments | `backend/tests/payments/test_payments_api.py` |
| AC6.2.3 | OK | u5-payments | `frontend/e2e/payments.spec.ts` |
| AC6.3.1 | OK | u5-payments | `backend/tests/payments/test_payment_service.py` |
| AC6.3.2 | OK | u5-payments | `backend/tests/payments/test_webhook_concurrency.py` |
| AC6.3.3 | OK | u5-payments | `backend/tests/payments/test_payments_api.py` |
| AC6.4.1 | OK | u5-payments | `backend/tests/payments/test_payment_service.py` |
| AC6.4.2 | OK | u5-payments | `backend/tests/payments/test_payment_service.py` |
| AC6.4.3 | OK | u5-payments | `backend/tests/payments/test_payment_service.py` |
| AC6.5.1 | OK | u5-payments | `frontend/src/components/payments/payment-confirmation.test.tsx` |
| AC6.5.2 | OK | u5-payments | `frontend/src/components/payments/payment-confirmation.test.tsx` |
| AC6.5.3 | OK | u5-payments | `frontend/src/components/payments/payment-confirmation.test.tsx` |
| AC7.1.1 | OK | u6-analysis-core | `backend/tests/analysis/test_analysis_flow.py` |
| AC7.1.2 | OK | u6-analysis-core | `backend/tests/analysis/test_analysis_flow.py` |
| AC7.1.3 | OK | u6-analysis-core | `backend/tests/analysis/test_start_concurrency.py` |
| AC7.1.4 | OK | u6-analysis-core | `backend/tests/analysis/test_analysis_flow.py` |
| AC7.10.1 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.10.2 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.11.1 | OK | u6-analysis-core | `frontend/src/components/analysis/analysis-progress.test.tsx` |
| AC7.11.2 | OK | u6-analysis-core | `backend/tests/analysis/test_analysis_flow.py` |
| AC7.11.3 | OK | u6-analysis-core | `frontend/src/components/analysis/analysis-progress.test.tsx` |
| AC7.2.1 | OK | u6-analysis-core | `frontend/src/components/analysis/analysis-progress.test.tsx` |
| AC7.2.2 | OK | u6-analysis-core | `frontend/src/components/analysis/analysis-progress.test.tsx` |
| AC7.2.3 | OK | u6-analysis-core | `frontend/e2e/analysis.spec.ts` |
| AC7.2.4 | OK | u6-analysis-core | `frontend/src/components/analysis/analysis-progress.test.tsx` |
| AC7.2.5 | OK | u6-analysis-core | `backend/tests/analysis/test_wiring_and_budget.py` |
| AC7.2.6 | Deferred | — | opt-in (eval): timed run on the real vendors before handover |
| AC7.3.1 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.3.2 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.4.1 | OK | u6-analysis-core | `backend/tests/analysis/test_report_writing.py` |
| AC7.4.2 | OK | u6-analysis-core | `backend/tests/analysis/test_report_writing.py` |
| AC7.4.3 | OK | u6-analysis-core | `backend/tests/analysis/test_report_writing.py` |
| AC7.5.1 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.5.2 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.5.3 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.6.1 | OK | u6-analysis-core | `backend/tests/analysis/test_analysis_flow.py` |
| AC7.6.2 | OK | u6-analysis-core | `backend/tests/analysis/test_analysis_flow.py` |
| AC7.6.3 | OK | u6-analysis-core | `backend/tests/analysis/test_analysis_flow.py` |
| AC7.6.4 | OK | u6-analysis-core | `backend/tests/analysis/test_wiring_and_budget.py` |
| AC7.6.5 | OK | u6-analysis-core | `backend/tests/analysis/test_analysis_flow.py` |
| AC7.7.1 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.7.2 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.8.1 | OK | u6-analysis-core | `backend/tests/analysis/test_measurement.py` |
| AC7.9.1 | OK | u6-analysis-core | `backend/tests/analysis/test_report_writing.py` |
| AC7.9.2 | OK | u6-analysis-core | `backend/tests/analysis/test_report_writing.py` |
| AC7.9.3 | OK | u6-analysis-core | `backend/tests/analysis/test_analysis_flow.py` |
| AC7.9.4 | Deferred | — | opt-in (eval): real-model narrative check before handover |
| AC8.1.1 | OK | u8-report-home | `backend/tests/report/test_report_api.py` |
| AC8.1.2 | OK | u8-report-home | `backend/tests/report/test_report_api.py` |
| AC8.1.3 | OK | u8-report-home | `backend/tests/report/test_report_api.py` |
| AC8.1.4 | OK | u8-report-home | `backend/tests/report/test_report_api.py` |
| AC8.2.1 | OK | u8-report-home | `backend/tests/report/test_report_api.py` |
| AC8.2.2 | OK | u8-report-home | `backend/tests/report/test_report_api.py` |
| AC8.2.3 | OK | u8-report-home | `backend/tests/report/test_report_api.py` |
| AC8.3.1 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.3.2 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.3.3 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.4.1 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.4.2 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.4.3 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.5.1 | OK | u8-report-home | `backend/tests/report/test_report_pdf.py` |
| AC8.5.2 | OK | u8-report-home | `backend/tests/report/test_report_pdf.py` |
| AC8.5.3 | OK | u8-report-home | `backend/tests/report/test_report_pdf.py` |
| AC8.6.1 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.7.1 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.7.2 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.7.3 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.7.4 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.7.5 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.8.1 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC8.8.2 | OK | u8-report-home | `frontend/src/components/report/report-screen.test.tsx` |
| AC9.1.1 | OK | u7-ai-images | `backend/tests/images/test_images_flow.py` |
| AC9.1.2 | OK | u7-ai-images | `backend/tests/images/test_images_flow.py` |
| AC9.1.3 | OK | u7-ai-images | `backend/tests/images/test_images_flow.py` |
| AC9.1.4 | Deferred | — | manual resemblance check on the real image vendor before handover (ASM-011) |
| AC9.2.1 | OK | u7-ai-images | `frontend/src/components/visuals/visuals-screen.test.tsx` |
| AC9.3.1 | OK | u7-ai-images | `frontend/src/components/visuals/visuals-screen.test.tsx` |
| AC9.4.1 | OK | u7-ai-images | `frontend/src/components/visuals/visuals-screen.test.tsx` |
| AC9.4.2 | OK | u7-ai-images | `backend/tests/images/test_images_flow.py` |
| AC9.5.1 | OK | u7-ai-images | `backend/tests/images/test_images_flow.py` |
| AC9.5.2 | OK | u7-ai-images | `backend/tests/images/test_images_flow.py` |
| AC9.5.3 | OK | u7-ai-images | `frontend/src/components/visuals/visuals-screen.test.tsx` |
| AC9.5.4 | OK | u7-ai-images | `backend/tests/images/test_images_flow.py` |
| AC9.5.5 | OK | u7-ai-images | `backend/tests/images/test_images_flow.py` |
| FR-001 | OK | requirement-test-map | `frontend/src/components/landing/landing-page.test.tsx` |
| FR-002 | OK | requirement-test-map | `backend/tests/identity/test_register_api.py` |
| FR-003 | OK | requirement-test-map | `backend/tests/onboarding/test_questionnaire_api.py` |
| FR-004 | OK | requirement-test-map | `backend/tests/onboarding/test_submit.py` |
| FR-005 | OK | requirement-test-map | `backend/tests/photos/test_photos_api.py` |
| FR-006 | OK | requirement-test-map | `backend/tests/photos/test_checks.py` |
| FR-007 | OK | requirement-test-map | `backend/tests/analysis/test_measurement.py` |
| FR-008 | OK | requirement-test-map | `backend/tests/analysis/test_report_writing.py` |
| FR-009 | OK | requirement-test-map | `backend/tests/report/test_report_api.py` |
| FR-010 | OK | requirement-test-map | `backend/tests/report/test_report_api.py` |
| FR-011 | OK | requirement-test-map | `backend/tests/report/test_report_api.py` |
| FR-012 | OK | requirement-test-map | `backend/tests/analysis/test_report_writing.py` |
| FR-013 | OK | requirement-test-map | `backend/tests/report/test_report_pdf.py` |
| FR-014 | OK | requirement-test-map | `backend/tests/report/test_report_api.py` |
| FR-015 | OK | u5-payments | `backend/tests/payments/test_payment_service.py` |
| FR-016 | OK | u5-payments | `backend/tests/payments/test_payments_api.py` |
| FR-017 | OK | requirement-test-map | `frontend/src/components/home/home-overview.test.tsx` |
| FR-018 | OK | requirement-test-map | `frontend/src/components/report/report-screen.test.tsx` |
| FR-019 | OK | u9-beauty-assistant | `backend/tests/chat/test_chat_api.py` |
| FR-020 | OK | requirement-test-map | `frontend/src/components/visuals/visuals-screen.test.tsx` |
| FR-021 | OK | requirement-test-map | `backend/tests/settings/test_settings_api.py` |
| FR-022 | OK | requirement-test-map | `backend/tests/images/test_images_flow.py` |
| FR1 | OK | group | `4 sub-requirements covered` |
| FR1.1 | OK | u10-journey-settings (via US2.1) | `frontend/src/components/landing/landing-page.test.tsx` |
| FR1.2 | OK | u10-journey-settings (via US2.1) | `frontend/src/components/landing/landing-page.test.tsx` |
| FR1.3 | OK | u10-journey-settings (via US2.2) | `frontend/src/components/landing/landing-page.test.tsx` |
| FR1.4 | OK | u10-journey-settings (via US2.1) | `frontend/src/components/landing/landing-page.test.tsx` |
| FR10 | OK | group | `5 sub-requirements covered` |
| FR10.1 | OK | u6-analysis-core (via US1.12) | `backend/tests/ai/test_fakes_and_selection.py` |
| FR10.2 | OK | u7-ai-images (via US9.1) | `backend/tests/images/test_images_flow.py` |
| FR10.3 | OK | u7-ai-images (via US9.2) | `frontend/src/components/visuals/visuals-screen.test.tsx` |
| FR10.4 | OK | u6-analysis-core (via US7.6) | `backend/tests/analysis/test_analysis_flow.py` |
| FR10.5 | OK | u7-ai-images (via US9.5) | `backend/tests/images/test_images_flow.py` |
| FR11 | OK | group | `4 sub-requirements covered` |
| FR11.1 | OK | u8-report-home (via US11.1) | `frontend/src/components/home/home-overview.test.tsx` |
| FR11.2 | OK | u8-report-home (via US11.2) | `frontend/src/components/app/app-header.test.tsx` |
| FR11.3 | OK | u8-report-home (via US11.1) | `frontend/src/components/home/home-overview.test.tsx` |
| FR11.4 | OK | u8-report-home (via US11.3) | `frontend/src/components/home/home-overview.test.tsx` |
| FR12 | OK | group | `4 sub-requirements covered` |
| FR12.1 | OK | u9-beauty-assistant (via US10.1) | `backend/tests/chat/test_chat_api.py` |
| FR12.2 | OK | u9-beauty-assistant (via US10.2) | `backend/tests/chat/test_chat_api.py` |
| FR12.3 | OK | u9-beauty-assistant (via US10.1) | `backend/tests/chat/test_chat_api.py` |
| FR12.4 | OK | u9-beauty-assistant (via US10.3) | `backend/tests/chat/test_chat_api.py` |
| FR13 | OK | group | `3 sub-requirements covered` |
| FR13.1 | OK | u10-journey-settings (via US11.4) | `backend/tests/settings/test_settings_api.py` |
| FR13.2 | OK | u2-session-security (via US11.5) | `backend/app/identity/password_change.py` |
| FR13.3 | OK | u10-journey-settings (via US11.6) | `backend/tests/settings/test_settings_api.py` |
| FR14 | OK | group | `2 sub-requirements covered` |
| FR14.1 | OK | u2-session-security (via US3.9) | `backend/app/identity/password_reset.py` |
| FR14.2 | OK | u2-session-security (via US3.7) | `frontend/src/components/app/user-menu.tsx` |
| FR2 | OK | group | `15 sub-requirements covered` |
| FR2.1 | OK | u1-walking-skeleton (via US3.1) | `backend/tests/identity/test_register_api.py` |
| FR2.10 | OK | u1-walking-skeleton (via US1.8) | `backend/app/identity/dependencies.py` |
| FR2.11 | OK | u2-session-security (via US3.6) | `backend/app/identity/sessions.py` |
| FR2.12 | OK | u2-session-security (via US3.9) | `backend/app/identity/password_reset.py` |
| FR2.13 | OK | u2-session-security (via US11.5) | `backend/app/identity/password_change.py` |
| FR2.14 | OK | u1-walking-skeleton (via US3.1) | `backend/tests/identity/test_register_api.py` |
| FR2.15 | OK | u1-walking-skeleton (via US1.4) | `.pre-commit-config.yaml` |
| FR2.2 | OK | u1-walking-skeleton (via US3.4) | `backend/tests/identity/test_login_verify_api.py` |
| FR2.3 | OK | u1-walking-skeleton (via US3.2) | `backend/tests/identity/test_codes.py` |
| FR2.4 | OK | u1-walking-skeleton (via US3.2) | `backend/tests/identity/test_codes.py` |
| FR2.5 | OK | u1-walking-skeleton (via US3.2) | `backend/tests/identity/test_codes.py` |
| FR2.6 | OK | u2-session-security (via US3.6) | `backend/app/identity/sessions.py` |
| FR2.7 | OK | u2-session-security (via US3.5) | `frontend/src/components/app/protected-route.tsx` |
| FR2.8 | OK | u2-session-security (via US3.7) | `frontend/src/components/app/user-menu.tsx` |
| FR2.9 | OK | u1-walking-skeleton (via US3.8) | `backend/tests/identity/test_me_and_routes.py` |
| FR3 | OK | group | `6 sub-requirements covered` |
| FR3.1 | OK | u1-walking-skeleton (via US1.9) | `frontend/src/lib/auth/store.ts` |
| FR3.2 | OK | u1-walking-skeleton (via US1.9) | `frontend/src/lib/auth/store.ts` |
| FR3.3 | OK | u2-session-security (via US3.5) | `frontend/src/components/app/protected-route.tsx` |
| FR3.4 | OK | u2-session-security (via US3.10) | `frontend/src/lib/auth/refresh-coordinator.ts` |
| FR3.5 | OK | u2-session-security (via US3.5) | `frontend/src/components/app/protected-route.tsx` |
| FR3.6 | OK | u1-walking-skeleton (via US1.3) | `.github/workflows/ci.yml` |
| FR4 | OK | group | `6 sub-requirements covered` |
| FR4.1 | OK | u3-onboarding (via US4.1) | `backend/app/onboarding/services.py` |
| FR4.2 | OK | u3-onboarding (via US4.2) | `backend/app/onboarding/definition.py` |
| FR4.3 | OK | u3-onboarding (via US4.2) | `backend/app/onboarding/definition.py` |
| FR4.4 | OK | u3-onboarding (via US4.3) | `frontend/src/components/onboarding/questionnaire-wizard.tsx` |
| FR4.5 | OK | u3-onboarding (via US4.2) | `backend/app/onboarding/definition.py` |
| FR4.6 | OK | u3-onboarding (via US4.2) | `backend/app/onboarding/definition.py` |
| FR5 | OK | group | `5 sub-requirements covered` |
| FR5.1 | OK | u4-photos (via US5.1) | `frontend/src/components/photos/photo-flow.test.tsx` |
| FR5.2 | OK | u4-photos (via US5.2) | `backend/tests/photos/test_photos_config.py` |
| FR5.3 | OK | u1-walking-skeleton (via US1.5) | `backend/app/platform/settings.py` |
| FR5.4 | OK | u4-photos (via US1.10) | `backend/tests/media/test_storage.py` |
| FR5.5 | OK | u4-photos (via US5.8) | `backend/tests/media/test_images.py` |
| FR6 | OK | group | `9 sub-requirements covered` |
| FR6.1 | OK | u4-photos (via US1.11) | `backend/tests/face/test_face_geometry.py` |
| FR6.2 | OK | u4-photos (via US5.5) | `backend/tests/photos/test_checks.py` |
| FR6.3 | OK | u4-photos (via US1.11) | `backend/tests/face/test_face_geometry.py` |
| FR6.4 | OK | u4-photos (via US5.6) | `backend/tests/photos/test_identity_decision.py` |
| FR6.5 | OK | u4-photos (via US5.6) | `backend/tests/photos/test_identity_decision.py` |
| FR6.6 | OK | u4-photos (via US5.11) | `frontend/src/components/photos/photo-flow.test.tsx` |
| FR6.7 | OK | u10-journey-settings (via US5.7) | `backend/tests/journey/test_next_step.py` |
| FR6.8 | OK | u4-photos (via US5.6) | `backend/tests/photos/test_identity_decision.py` |
| FR6.9 | OK | u4-photos (via US5.5) | `backend/tests/photos/test_checks.py` |
| FR7 | OK | group | `6 sub-requirements covered` |
| FR7.1 | OK | u5-payments (via US6.1) | `frontend/src/components/payments/payment-screen.test.tsx` |
| FR7.2 | OK | u5-payments (via US6.2) | `backend/tests/payments/test_stripe_gateway.py` |
| FR7.3 | OK | u1-walking-skeleton (via US1.5) | `backend/app/platform/settings.py` |
| FR7.4 | OK | u5-payments (via US6.3) | `backend/tests/payments/test_payment_service.py` |
| FR7.5 | OK | u5-payments (via US6.3) | `backend/tests/payments/test_payment_service.py` |
| FR7.6 | OK | u5-payments (via US6.4) | `backend/tests/payments/test_payment_service.py` |
| FR8 | OK | group | `7 sub-requirements covered` |
| FR8.1 | OK | u6-analysis-core (via US7.1) | `backend/tests/analysis/test_analysis_flow.py` |
| FR8.2 | OK | u6-analysis-core (via US1.7) | `backend/tests/jobs/test_queue.py` |
| FR8.3 | OK | u4-photos (via US1.11) | `backend/tests/face/test_face_geometry.py` |
| FR8.4 | OK | u6-analysis-core (via US7.4) | `backend/tests/analysis/test_report_writing.py` |
| FR8.5 | OK | u6-analysis-core (via US7.4) | `backend/tests/analysis/test_report_writing.py` |
| FR8.6 | OK | u6-analysis-core (via US7.4) | `backend/tests/analysis/test_report_writing.py` |
| FR8.7 | OK | u6-analysis-core (via US7.9) | `backend/tests/analysis/test_report_writing.py` |
| FR9 | OK | group | `8 sub-requirements covered` |
| FR9.1 | OK | u8-report-home (via US8.1) | `backend/tests/report/test_report_api.py` |
| FR9.2 | OK | u6-analysis-core (via US7.9) | `backend/tests/analysis/test_report_writing.py` |
| FR9.3 | OK | u8-report-home (via US8.1) | `backend/tests/report/test_report_api.py` |
| FR9.4 | OK | u6-analysis-core (via US7.9) | `backend/tests/analysis/test_report_writing.py` |
| FR9.5 | OK | u6-analysis-core (via US7.5) | `backend/tests/analysis/test_measurement.py` |
| FR9.6 | OK | u8-report-home (via US8.6) | `frontend/src/components/report/report-screen.test.tsx` |
| FR9.7 | OK | u8-report-home (via US8.5) | `backend/tests/report/test_report_pdf.py` |
| FR9.8 | OK | u8-report-home (via US8.1) | `backend/tests/report/test_report_api.py` |
| NFR-001 | OK | u1-walking-skeleton | `scripts/check-app-independence.sh` |
| NFR-006 | OK | u1-walking-skeleton | `frontend/src/lib/auth/store.test.ts` |
| NFR-007 | OK | u4-photos | `backend/tests/face/test_face_geometry.py` |
| NFR-008 | OK | u6-analysis-core | `backend/tests/ai/test_fakes_and_selection.py` |
| NFR-009 | OK | u5-payments | `backend/tests/payments/test_stripe_gateway.py` |
| NFR-010 | N/A | — | no host assumed or built (client-confirmed); nothing to test |
| NFR-011 | OK | all units | `backend/pyproject.toml` |
| NFR-012 | OK | u1-walking-skeleton | `backend/tests/platform/test_smtp.py` |
| NFR-013 | OK | u7-ai-images | `backend/tests/ai/test_fakes_and_selection.py` |
| NFR1 | OK | u1-walking-skeleton (via US1.1) | `README.md` |
| NFR10 | OK | u6-analysis-core (via US1.12) | `backend/tests/ai/test_fakes_and_selection.py` |
| NFR11 | OK | u1-walking-skeleton (via US1.1) | `README.md` |
| NFR12 | OK | u1-walking-skeleton (via US1.2) | `docker-compose.yml` |
| NFR2 | OK | u1-walking-skeleton (via US3.1) | `backend/tests/identity/test_register_api.py` |
| NFR3 | OK | u1-walking-skeleton (via US1.4) | `.pre-commit-config.yaml` |
| NFR4 | OK | u6-analysis-core (via US1.7) | `backend/tests/jobs/test_queue.py` |
| NFR5 | OK | u1-walking-skeleton (via US1.6) | `backend/app/platform/email/__init__.py` |
| NFR6 | OK | u1-walking-skeleton (via US1.5) | `backend/app/platform/settings.py` |
| NFR7 | OK | u1-walking-skeleton (via US1.1) | `README.md` |
| NFR8 | OK | u1-walking-skeleton (via US1.3) | `.github/workflows/ci.yml` |
| NFR9 | OK | u10-journey-settings (via US1.13) | `backend/tests/traceability/test_requirement_map.py` |
