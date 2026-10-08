# Code Summary — U9 AI Beauty Assistant

## What was built
- Backend `app/chat/`: grounding from the stored report + non-medical answers only, medical-decline instruction on every request, `GET`/`POST /chat/messages` (402/404/429/502/504), migration `0009_u9_chat` (`chat_messages`, `chat_usage`), atomic per-UTC-day limit reservation released on AI failure.
- Frontend `/chat`: empty state, history, reply indicator, `aria-live` reply, error toast keeping the message, limit-reached message, short-height layout for phone keyboards.
- Checkpoint journey now chats; `e2e/chat.spec.ts`; chat in the axe list; FR-019 mapped to tests; opt-in `(eval)` suite (`RUN_CHAT_EVAL=1`).
- Full file list: `source-manifest.json`.

## Decisions ([Decided by delivery team])
- Contract path `/chat/messages` (plan said `/chat`). `CHAT_DAILY_LIMIT=50`, `CHAT_HISTORY_MESSAGES=20`, `CHAT_TIMEOUT_SECONDS=45`. Only errors toast.

## Tests
- Backend 938 passed (5 eval skipped), 98.32%; frontend 363 passed, 96.9%; all linters clean; requirement map OK; `verify-skeleton.sh` 53 s.
