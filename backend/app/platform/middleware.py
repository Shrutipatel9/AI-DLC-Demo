"""HTTP middleware stack (security design section 1, observability design section 2).

Order, outermost first (installed by :func:`install_middleware`):

1. ``CORSMiddleware``        — outermost (U2 NFD post-review R-06), so every response,
   including 403, 429 and 5xx, carries the CORS headers. Origins are the normalised
   ``CSRF_ALLOWED_ORIGINS`` (default ``FRONTEND_ORIGIN``); methods GET, POST, OPTIONS.
2. ``RequestIdMiddleware``   — request id on the log context and the response.
3. ``AccessLogMiddleware``   — one ``http.request`` line + RED metrics per request.
4. ``SecurityHeadersMiddleware`` — nosniff, no-referrer, no-store on /auth/*, HSTS.
5. ``BodySizeGuardMiddleware``   — 16 KB cap on /auth/* bodies (422 BODY_TOO_LARGE), a
   second instance capping /photos/* uploads (413 PHOTO_TOO_LARGE, U4), and a third capping
   /payments/* bodies at 256 KB (413 VALIDATION_FAILED BODY_TOO_LARGE, U5).
6. ``CatchAllMiddleware``    — unexpected exceptions -> 500 INTERNAL_ERROR (logged once).

All are pure ASGI middlewares, so they work with streaming bodies and keep the scope
shared (the access log reads the matched route template from it).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.platform.errors import ErrorCode, error_body, internal_error_response
from app.platform.metrics import Metrics
from app.platform.request_id import RequestIdMiddleware
from app.platform.settings import Settings

access_logger = logging.getLogger("http.access")
error_logger = logging.getLogger("http.errors")

UNMATCHED_ROUTE = "unmatched"
AUTH_PREFIX = "/auth"
HSTS_VALUE = "max-age=31536000; includeSubDomains"

CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "OPTIONS"]  # PUT: onboarding answers (U3)
CORS_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "X-Requested-With",
    "X-Refresh-Attempt",
    "X-Request-ID",
]
CORS_EXPOSED_HEADERS = ["Retry-After", "X-Request-ID"]


def _is_auth_path(path: str) -> bool:
    return path == AUTH_PREFIX or path.startswith(AUTH_PREFIX + "/")


def route_label(scope: Scope) -> str:
    """Return the matched route template, or ``unmatched`` (bounded cardinality)."""
    route = scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return UNMATCHED_ROUTE


class AccessLogMiddleware:
    """Writes one INFO ``http.request`` line per request and records RED metrics."""

    def __init__(self, app: ASGIApp, metrics: Metrics | None = None) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process one ASGI call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def capture_status(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            elapsed = time.perf_counter() - started
            route = route_label(scope)
            method = str(scope.get("method", "GET"))
            status = status_holder["status"]
            access_logger.info(
                "request finished",
                extra={
                    "event": "http.request",
                    "route": route,
                    "method": method,
                    "status": status,
                    "durationMs": round(elapsed * 1000, 2),
                },
            )
            if self.metrics is not None:
                self.metrics.observe_request(route, method, status, elapsed)


class SecurityHeadersMiddleware:
    """Adds security headers to every response (NFR2.13, NFR3.5)."""

    def __init__(self, app: ASGIApp, *, hsts: bool) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process one ASGI call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_auth = _is_auth_path(str(scope.get("path", "")))

        async def add_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                if is_auth:
                    headers["Cache-Control"] = "no-store"
                if self.hsts:
                    headers["Strict-Transport-Security"] = HSTS_VALUE
            await send(message)

        await self.app(scope, receive, add_headers)


@dataclass(frozen=True)
class BodyRejection:
    """The response for an over-sized body."""

    status_code: int
    code: ErrorCode
    message: str
    details: tuple[dict[str, str], ...] = ()


AUTH_BODY_REJECTION = BodyRejection(
    422,
    ErrorCode.VALIDATION_FAILED,
    "The request is too large.",
    ({"field": "body", "reason": "BODY_TOO_LARGE"},),
)
#: Photo uploads (U4, AC5.2.3): 413 PHOTO_TOO_LARGE before the multipart body is parsed.
PHOTO_BODY_REJECTION = BodyRejection(
    413, ErrorCode.PHOTO_TOO_LARGE, "This photo is too large. Please choose a smaller photo."
)
PHOTOS_PREFIX = "/photos"
#: Payment requests (U5): the Stripe webhook is the only one with a body; Checkout session
#: events are a few KB, so 256 KB is generous. Larger bodies get 413 before any parsing.
PAYMENTS_PREFIX = "/payments"
PAYMENTS_MAX_BODY_BYTES = 256 * 1024
PAYMENTS_BODY_REJECTION = BodyRejection(
    413,
    ErrorCode.VALIDATION_FAILED,
    "The request is too large.",
    ({"field": "body", "reason": "BODY_TOO_LARGE"},),
)
#: Multipart framing and the small form fields around the file.
MULTIPART_OVERHEAD_BYTES = 64 * 1024


class BodySizeGuardMiddleware:
    """Caps request bodies under ``prefix`` (default /auth) at ``max_bytes``.

    Counts streamed bytes, so it works without ``Content-Length``. An oversized /auth body
    gets 422 ``VALIDATION_FAILED`` with ``details.reason = "BODY_TOO_LARGE"`` (plan decision
    D4); the photo instance answers 413 ``PHOTO_TOO_LARGE`` instead (U4).
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        max_bytes: int,
        prefix: str = AUTH_PREFIX,
        rejection: BodyRejection | None = None,
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.prefix = prefix
        self.rejection = rejection or AUTH_BODY_REJECTION

    def _applies(self, path: str) -> bool:
        return path == self.prefix or path.startswith(self.prefix + "/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process one ASGI call."""
        if scope["type"] != "http" or not self._applies(str(scope.get("path", ""))):
            await self.app(scope, receive, send)
            return

        declared = self._declared_length(scope)
        if declared is not None and declared > self.max_bytes:
            await self._reject(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        more = True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            chunks.append(body)
            more = bool(message.get("more_body", False))

        buffered = b"".join(chunks)
        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    def _declared_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        rejection = self.rejection
        response = JSONResponse(
            status_code=rejection.status_code,
            content=error_body(rejection.code, rejection.message, rejection.details),
        )
        await response(scope, receive, send)


class CatchAllMiddleware:
    """Turns an unexpected exception into the generic 500 body and logs it once.

    It sits inside CORS and the security headers, so the browser can read the error.
    The stack trace goes to the log (``http.unhandled``), never to the response.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process one ASGI call."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def track(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, track)
        except Exception as exc:
            error_logger.error(
                "unhandled error",
                exc_info=True,
                extra={
                    "event": "http.unhandled",
                    "route": route_label(scope),
                    "errorClass": type(exc).__name__,
                },
            )
            if started:
                raise
            await internal_error_response()(scope, receive, send)


Middleware = Callable[[Scope, Receive, Send], Awaitable[None]]


def install_middleware(app: FastAPI, settings: Settings, metrics: Metrics | None) -> None:
    """Install the stack in the documented order (``add_middleware`` wraps outward)."""
    app.add_middleware(CatchAllMiddleware)
    app.add_middleware(
        BodySizeGuardMiddleware,
        max_bytes=settings.photo_max_upload_bytes + MULTIPART_OVERHEAD_BYTES,
        prefix=PHOTOS_PREFIX,
        rejection=PHOTO_BODY_REJECTION,
    )
    app.add_middleware(
        BodySizeGuardMiddleware,
        max_bytes=PAYMENTS_MAX_BODY_BYTES,
        prefix=PAYMENTS_PREFIX,
        rejection=PAYMENTS_BODY_REJECTION,
    )
    app.add_middleware(BodySizeGuardMiddleware, max_bytes=settings.auth_max_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware, hsts=not settings.is_development)
    app.add_middleware(AccessLogMiddleware, metrics=metrics)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.csrf_origins,
        allow_credentials=True,
        allow_methods=CORS_ALLOWED_METHODS,
        allow_headers=CORS_ALLOWED_HEADERS,
        expose_headers=CORS_EXPOSED_HEADERS,
        max_age=600,
    )
