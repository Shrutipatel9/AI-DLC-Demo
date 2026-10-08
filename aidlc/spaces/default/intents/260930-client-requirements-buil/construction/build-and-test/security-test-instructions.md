# Security Test Instructions

- Secrets: `gitleaks` on the working tree (pre-commit hook and `verify.sh`).
- Dependencies: `pip-audit` (backend lockfile) and `pnpm audit` (frontend), run by `verify.sh`/CI; Dependabot enabled.
- Static: Ruff `S` (bandit) rules and ESLint security plugins in lint.
- Auth: deny-list check (no third-party auth / Supabase), app-independence check, CSRF/CORS tests, refresh-token reuse detection, httpOnly cookie, no Web Storage for auth state (identity and frontend auth store tests).
- Ownership: every resource returns 404 for another user (photos/media, report, images, chat, settings tests); paywall 402 before analysis/report/chat.
- Privacy: canary tests prove no medical answer reaches AI requests (report writing and chat) and no canary text reaches logs.
