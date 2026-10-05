"""JSON formatter, allow-list and masking (NFR5.6, NFR5.12, NFR3.2, BR6.3; AC1.8.3)."""

from __future__ import annotations

import json
import logging
import sys

import pytest

from app.platform.logging import JsonFormatter, configure_logging, mask_email


def _record(message: str = "hello", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord("test.logger", logging.INFO, __file__, 1, message, None, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_formatter_emits_only_allow_listed_fields() -> None:
    record = _record(
        event="auth.code.sent",
        userId="u-1",
        purpose="signup",
        password="Sunrise2026x",  # not allow-listed -> dropped
        code="123456",  # not allow-listed -> dropped
        token="eyJ.secret",  # not allow-listed -> dropped
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["event"] == "auth.code.sent"
    assert payload["userId"] == "u-1"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["timestamp"].endswith("Z")
    for forbidden in ("password", "code", "token"):
        assert forbidden not in payload
    text = JsonFormatter().format(record)
    assert "Sunrise2026x" not in text
    assert "123456" not in text
    assert "eyJ.secret" not in text


@pytest.mark.parametrize(
    ("email", "masked"),
    [
        ("maya@example.com", "m•••@example.com"),
        ("  A@b.co ", "A•••@b.co"),
        ("not-an-email", "•••"),
        ("@example.com", "•••"),
    ],
)
def test_mask_email(email: str, masked: str) -> None:
    assert mask_email(email) == masked


def test_mask_email_none_passthrough() -> None:
    assert mask_email(None) is None


def test_formatter_masks_unmasked_email_as_safety_net() -> None:
    payload = json.loads(JsonFormatter().format(_record(email="maya@example.com")))
    assert payload["email"] == "m•••@example.com"
    already = json.loads(JsonFormatter().format(_record(email="m•••@example.com")))
    assert already["email"] == "m•••@example.com"


def test_exception_trace_is_included_in_logs_only() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord("x", logging.ERROR, __file__, 1, "failed", None, sys.exc_info())
    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exception"]


def test_configure_logging_is_idempotent_and_disables_uvicorn_access() -> None:
    root = logging.getLogger()
    before = len(root.handlers)
    configure_logging("WARNING")
    configure_logging("INFO")
    marked = [h for h in root.handlers if getattr(h, "_app_json_handler", False)]
    assert len(marked) == 1
    assert root.level == logging.INFO
    assert logging.getLogger("uvicorn.access").disabled is True
    for handler in marked:
        root.removeHandler(handler)
    assert len(root.handlers) <= before + 1
