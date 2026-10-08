"""Migration round-trip for the checkpoint run: upgrade to head, downgrade to base, upgrade again.

``scripts/verify-skeleton.sh`` runs this in one Python process instead of three ``alembic``
invocations (each pays the interpreter and import start-up). It proves the same thing: every
migration applies, reverses cleanly and applies again to the throwaway ``app_e2e`` database.

    uv run python -m tools.migration_roundtrip          # uses E2E_DATABASE_URL
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic.config import Config

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    """Run upgrade, downgrade and upgrade against ``E2E_DATABASE_URL``; return the exit code."""
    url = os.environ.get("E2E_DATABASE_URL", "")
    if not url:
        print("E2E_DATABASE_URL is not set (see scripts/ci-env.sh).", file=sys.stderr)
        return 1
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    print("Migration round-trip OK (head -> base -> head).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
