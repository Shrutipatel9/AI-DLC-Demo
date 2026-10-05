"""Small helpers shared by tests (no fixtures here; see conftest.py)."""

from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import tempfile
from pathlib import Path
from typing import Any

from app.platform.settings import Settings


def random_key(size: int = 48) -> str:
    """A fresh base64 key of ``size`` random bytes."""
    return base64.b64encode(secrets.token_bytes(size)).decode()


def base_env(**overrides: Any) -> dict[str, str]:
    """A complete, valid settings environment for APP_ENV=test (strings only)."""
    values: dict[str, Any] = {
        "APP_ENV": "test",
        "DATABASE_URL": os.environ.get(
            "TEST_DATABASE_URL", "postgresql+psycopg://app:app@127.0.0.1:5432/app_test"
        ),
        "FRONTEND_ORIGIN": "http://localhost:3000",
        "JWT_SIGNING_KEYS": json.dumps({"k1": random_key()}),
        "JWT_ACTIVE_KID": "k1",
        "CODE_HMAC_KEY": random_key(),
        "EMAIL_HASH_KEY": random_key(),
        "REFRESH_COOKIE_SECURE": "false",
        "EMAIL_BACKEND": "fake",
        "RATE_LIMIT_BACKEND": "memory",
        # The limiter's own tests rely on the production limits, so they are set
        # explicitly here; scripts/ci-env.sh raises them only for the e2e servers (U2 D10).
        "AUTH_RATE_LIMIT_PER_MINUTE": 20,
        "REFRESH_RATE_LIMIT_PER_MINUTE": 60,
        "LOG_LEVEL": "INFO",
        # U5: a test price and the fake provider; the default test run never calls Stripe.
        "REPORT_PRICE_AMOUNT": 1999,
        "REPORT_PRICE_CURRENCY": "USD",
        "PAYMENT_PROVIDER": "fake",
        # Never the developer's var/media: tests that read files set their own tmp_path.
        "MEDIA_ROOT": os.environ.get(
            "TEST_MEDIA_ROOT", str(Path(tempfile.gettempdir()) / "facial-analysis-test-media")
        ),
    }
    values.update(overrides)
    return {key: str(value) for key, value in values.items() if value is not None}


def make_settings(**overrides: Any) -> Settings:
    """Build Settings from ``base_env`` without reading the process environment's .env."""
    return Settings(_env_file=None, **base_env(**overrides))  # type: ignore[arg-type]


def free_port() -> int:
    """Ask the OS for a free localhost TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
