"""Structured JSON logging with an allow-list of fields (NFR5.6, NFR5.12, NFR3.2, BR6.3).

- One JSON object per line on stdout.
- Only allow-listed keys are emitted; anything else passed in ``extra`` is dropped.
- ``mask_email`` is the only way an email may enter a log. As a safety net the formatter
  also masks any ``email`` value that is not masked yet.
- Request and response bodies are never logged.

Usage::

    logger.info("code sent", extra={"event": "auth.code.sent", "userId": str(user_id)})
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import UTC, datetime
from types import TracebackType
from typing import Any

from sqlalchemy.exc import DBAPIError

from app.platform.request_id import current_request_id

ALLOWED_FIELDS: tuple[str, ...] = (
    "timestamp",
    "level",
    "logger",
    "message",
    "requestId",
    "event",
    "userId",
    "email",
    "purpose",
    "route",
    "method",
    "status",
    "durationMs",
    "attemptsLeft",
    "attempt",
    # U2 security events (observability design, NFD post-review R-07). Never secrets.
    "familyId",
    "reason",
    "count",
    "sent",
    "outcome",
    "adapter",
    "errorClass",
    "exception",
)
_EXTRA_FIELDS = frozenset(ALLOWED_FIELDS) - {"timestamp", "level", "logger", "message"}
MASK = "•••"


def mask_email(email: str | None) -> str | None:
    """Mask an email for display or logs: first character, bullets, then the domain.

    ``maya@example.com`` -> ``m•••@example.com`` (BR2.8). Text without ``@`` is fully
    masked.
    """
    if email is None:
        return None
    local, sep, domain = email.strip().partition("@")
    if not sep or not local:
        return MASK
    return f"{local[0]}{MASK}@{domain}"


ExcInfo = tuple[type[BaseException], BaseException, TracebackType | None]


def _database_error(exc: BaseException | None) -> DBAPIError | None:
    """The first database error in the exception chain, if any."""
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        if isinstance(exc, DBAPIError):
            return exc
        seen.add(id(exc))
        exc = exc.__cause__ or exc.__context__
    return None


def safe_exception_text(exc_info: ExcInfo) -> str | None:
    """Render a database exception without its message, or ``None`` for other exceptions.

    PostgreSQL puts the offending values in the error ``DETAIL`` (for example
    ``Key (lower(email))=(maya@example.com) already exists``), and ``hide_parameters`` only
    hides SQLAlchemy's own parameter list. So for database errors only the stack, the
    exception class and the SQLSTATE are logged, never the message (U2 NFR3.2).
    """
    _, exc, tb = exc_info
    database_error = _database_error(exc)
    if database_error is None:
        return None
    sqlstate = getattr(database_error.orig, "sqlstate", None) or "unknown"
    stack = "".join(traceback.format_tb(tb))
    return (
        "Traceback (most recent call last):\n"
        f"{stack}{type(database_error).__name__} (sqlstate {sqlstate}): details hidden"
    )


class JsonFormatter(logging.Formatter):
    """Render records as JSON, keeping only allow-listed fields."""

    def format(self, record: logging.LogRecord) -> str:
        """Format one record."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "requestId", None) or current_request_id()
        if request_id:
            payload["requestId"] = request_id
        for key in _EXTRA_FIELDS:
            if key in ("requestId", "exception"):
                continue
            if key in record.__dict__:
                value = record.__dict__[key]
                if key == "email" and isinstance(value, str) and MASK not in value:
                    value = mask_email(value)
                payload[key] = value
        if record.exc_info and record.exc_info[1] is not None:
            exc_info: ExcInfo = record.exc_info
            payload["exception"] = safe_exception_text(exc_info) or self.formatException(exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger and silence duplicate access logs."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    for existing in list(root.handlers):
        if getattr(existing, "_app_json_handler", False):
            root.removeHandler(existing)
    handler._app_json_handler = True  # type: ignore[attr-defined]  # marker for idempotence
    root.addHandler(handler)
    root.setLevel(level)
    # Uvicorn's own access log would duplicate our http.request line (observability §2).
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
