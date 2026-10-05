"""Prometheus metrics (NFR5.10, observability design section 4).

Series are always collected in a dedicated registry. The ``/metrics`` endpoint is a
separate ASGI sub-app, mounted only when ``METRICS_ENABLED=true``, and it answers only
clients whose socket address is inside ``METRICS_ALLOW_CIDRS`` (others get 403).
Labels never contain user ids or emails; ``route`` is a route template or ``unmatched``.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram
from prometheus_client.exposition import generate_latest
from starlette.responses import JSONResponse, Response
from starlette.types import Receive, Scope, Send

from app.platform.errors import ErrorCode, error_body

DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class Metrics:
    """All application metric series in one registry."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.http_requests_total = Counter(
            "http_requests_total",
            "HTTP requests by route template, method and status.",
            ["route", "method", "status"],
            registry=self.registry,
        )
        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration by route template and method.",
            ["route", "method"],
            buckets=DURATION_BUCKETS,
            registry=self.registry,
        )
        self.auth_codes_sent_total = Counter(
            "auth_codes_sent_total", "One-time codes emailed.", ["purpose"], registry=self.registry
        )
        self.auth_code_failures_total = Counter(
            "auth_code_failures_total",
            "Wrong one-time codes entered.",
            ["purpose"],
            registry=self.registry,
        )
        self.auth_lockouts_total = Counter(
            "auth_lockouts_total",
            "Code verification lockouts started.",
            ["purpose"],
            registry=self.registry,
        )
        self.rate_limited_total = Counter(
            "rate_limited_total",
            "Requests refused by the per-IP limiter.",
            ["route"],
            registry=self.registry,
        )
        # --- U2 session security (NFR5.10). Labels never carry user or family ids.
        self.auth_refresh_total = Counter(
            "auth_refresh_total",
            "Refresh exchanges by outcome (ok, recovered, expired, invalid, revoked, "
            "reuse_detected, csrf_refused).",
            ["outcome"],
            registry=self.registry,
        )
        self.auth_sessions_revoked_total = Counter(
            "auth_sessions_revoked_total",
            "Usable refresh sessions revoked, by reason.",
            ["reason"],
            registry=self.registry,
        )
        self.auth_password_resets_total = Counter(
            "auth_password_resets_total",
            "Password-reset funnel steps (requested, code_verified, completed).",
            ["step"],
            registry=self.registry,
        )
        self.auth_password_changes_total = Counter(
            "auth_password_changes_total",
            "Signed-in password changes by outcome (changed, wrong_current).",
            ["outcome"],
            registry=self.registry,
        )
        self.email_send_failures_total = Counter(
            "email_send_failures_total",
            "Email sends that failed after retries.",
            ["reason"],
            registry=self.registry,
        )

    def observe_request(self, route: str, method: str, status: int, seconds: float) -> None:
        """Record one finished HTTP request."""
        self.http_requests_total.labels(route=route, method=method, status=str(status)).inc()
        self.http_request_duration_seconds.labels(route=route, method=method).observe(seconds)

    def render(self) -> bytes:
        """Return the Prometheus text exposition of every series."""
        return bytes(generate_latest(self.registry))


class MetricsEndpoint:
    """ASGI app serving ``/metrics`` to allow-listed client addresses only."""

    def __init__(self, metrics: Metrics, allow_cidrs: Iterable[str]) -> None:
        self._metrics = metrics
        self._networks = [ipaddress.ip_network(cidr, strict=False) for cidr in allow_cidrs]

    def is_allowed(self, client_host: str | None) -> bool:
        """True when the socket peer address is inside an allowed network."""
        if not client_host:
            return False
        try:
            address = ipaddress.ip_address(client_host)
        except ValueError:
            return False
        return any(address in network for network in self._networks)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve the exposition or 403."""
        client = scope.get("client")
        host = client[0] if client else None
        response: Response
        if not self.is_allowed(host):
            response = JSONResponse(
                status_code=403,
                content=error_body(ErrorCode.NOT_FOUND, "Not allowed."),
            )
        else:
            response = Response(self._metrics.render(), media_type=CONTENT_TYPE_LATEST)
        await response(scope, receive, send)
