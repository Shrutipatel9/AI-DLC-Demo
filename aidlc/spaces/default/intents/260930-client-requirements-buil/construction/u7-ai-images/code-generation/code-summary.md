# Code Summary — U7 AI images

## What was built
- Backend `app/images/` (24-slot prompt catalog, generator with auto retries and rate-limit back-off, manual retry service, `GET /images`, `POST /images/{slotId}/retry`) and `app/analysis/slots.py`; the worker's image step now generates real images; migration `0007_u7_images`.
- Frontend `/visuals` (hairstyles, outfits, 4-card aging stack, AI labels, retry), linked from the finished progress screen and Home.
- The analysis `@checkpoint` journey now opens `/visuals`; a failed-slot → retry case lives in `e2e/analysis.spec.ts`.
- Full file list: `source-manifest.json`.

## Decisions ([Decided by delivery team])
- Prompt wording is ours, versioned in `app/images/catalog.py`. Settings `AI_IMAGE_AUTO_RETRIES=3`, `AI_IMAGE_MANUAL_RETRY_LIMIT=3`, `AI_IMAGE_FIDELITY=high`. A failed manual retry still counts; past the limit → 409 `IMAGE_RETRY_NOT_AVAILABLE`, no vendor call.
- Known edge: if the API dies mid manual retry, that slot stays "generating" until retried again.
- AC9.1.4 (resemblance on real vendor) is the manual check before handover (ASM-011).

## Tests
- Backend 864 passed, 98.29%; frontend 298 passed, 96.57%; all linters clean; `verify-skeleton.sh` exit 0 in ~76 s.
