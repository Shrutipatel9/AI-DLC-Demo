"""Print the API's OpenAPI document as JSON (contract Q6, plan decision D11).

It calls ``app.openapi()`` in-process and never fetches ``/openapi.json``, so it works in
every environment. Throwaway keys are generated in memory; nothing connects to a database.

    uv run python -m tools.export_openapi path/to/openapi.json
"""

from __future__ import annotations

import base64
import json
import secrets
import sys
from pathlib import Path

from app.main import create_app
from app.platform.email.fake import RecordingEmailSender
from app.platform.settings import Settings


def _key() -> str:
    return base64.b64encode(secrets.token_bytes(48)).decode()


def build_document() -> dict[str, object]:
    """Build the OpenAPI document from the application code."""
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://openapi:openapi@127.0.0.1:1/openapi",
        FRONTEND_ORIGIN="http://localhost:3000",
        JWT_SIGNING_KEYS=json.dumps({"export": _key()}),
        JWT_ACTIVE_KID="export",
        CODE_HMAC_KEY=_key(),
        EMAIL_HASH_KEY=_key(),
        REFRESH_COOKIE_SECURE=False,
        EMAIL_BACKEND="fake",
        RATE_LIMIT_BACKEND="memory",
        CHECK_MIGRATIONS_AT_STARTUP=False,
        REPORT_PRICE_AMOUNT=1,
        REPORT_PRICE_CURRENCY="USD",
        PAYMENT_PROVIDER="fake",
    )
    app = create_app(settings, email_sender=RecordingEmailSender("test"))
    return app.openapi()


def main(argv: list[str] | None = None) -> int:
    """Write the document as UTF-8 JSON to the path given on the command line."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        sys.stderr.write("usage: python -m tools.export_openapi OUTPUT.json\n")
        return 2
    document = json.dumps(build_document(), indent=2, sort_keys=True, ensure_ascii=False)
    Path(args[0]).write_text(document + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
