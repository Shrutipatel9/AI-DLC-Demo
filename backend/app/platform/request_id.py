"""Request correlation id (NFR5.7).

The id comes from an incoming ``X-Request-ID`` header only when it is a canonical UUID
(36 characters); anything else is replaced by a new UUID4, which prevents log injection
through the header. The id is stored in a context variable for logging and error
bodies, and returned in the ``X-Request-ID`` response header.
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "x-request-id"
_CANONICAL_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str:
    """Return the current request id, or a fresh one outside a request."""
    current = _request_id.get()
    return current if current is not None else str(uuid.uuid4())


def current_request_id() -> str | None:
    """Return the current request id, or ``None`` outside a request (used by logging)."""
    return _request_id.get()


def accept_or_generate(candidate: str | None) -> str:
    """Return ``candidate`` lower-cased if it is a canonical UUID, else a new UUID4."""
    if candidate and _CANONICAL_UUID.fullmatch(candidate):
        return candidate.lower()
    return str(uuid.uuid4())


class RequestIdMiddleware:
    """Outermost middleware: assigns the request id and echoes it on the response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process one ASGI call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = None
        for name, value in scope.get("headers", []):
            if name.decode("latin-1").lower() == REQUEST_ID_HEADER:
                incoming = value.decode("latin-1")
                break
        request_id = accept_or_generate(incoming)
        scope.setdefault("state", {})["request_id"] = request_id
        token = _request_id.set(request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            _request_id.reset(token)
