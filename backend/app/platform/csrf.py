"""CSRF check for the cookie-authenticated endpoints (U2 BR2.5, NFR2.7, AUTH-013).

``/auth/refresh`` and ``/auth/logout`` are authenticated by the httpOnly refresh cookie
alone, so they need their own CSRF defence. The dependency refuses the request with 403
``CSRF_CHECK_FAILED`` **before the cookie is read**, so a refused request changes no session:

1. ``X-Requested-With`` must be exactly ``XMLHttpRequest`` (a cross-site form cannot set it,
   and a cross-site ``fetch`` that sets it needs a CORS preflight, which only allow-listed
   origins pass);
2. the request origin comes from ``Origin``, or, when ``Origin`` is absent, from the scheme
   and host of ``Referer``;
3. ``Origin: null``, a missing origin, or any origin not in ``CSRF_ALLOWED_ORIGINS`` (after
   normalisation to ``scheme://host[:port]``) is refused (FD post-review R-08).

Route order on the cookie endpoints is CORS -> CSRF -> refresh rate limit -> handler.
"""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from fastapi import Request

from app.platform.errors import CsrfCheckFailed
from app.platform.metrics import Metrics
from app.platform.settings import Settings, normalise_origin

logger = logging.getLogger("platform.csrf")

REQUESTED_WITH = "XMLHttpRequest"


def request_origin(origin: str | None, referer: str | None) -> str | None:
    """The normalised origin of a request, or ``None`` when it cannot be trusted.

    ``Origin`` wins; ``Referer`` is used only when ``Origin`` is absent. ``null`` and
    anything that is not an http(s) origin give ``None``.
    """
    candidate = origin
    if candidate is None and referer:
        parts = urlsplit(referer)
        candidate = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None
    if candidate is None or candidate.strip().lower() == "null":
        return None
    try:
        return normalise_origin(candidate)
    except ValueError:
        return None


class RequireCsrf:
    """FastAPI dependency that enforces the CSRF rules on one route.

    Args:
        route: Route template (for logs).
        count_refresh: Count refusals as ``auth_refresh_total{outcome="csrf_refused"}``.
    """

    def __init__(self, route: str, *, count_refresh: bool = False) -> None:
        self.route = route
        self.count_refresh = count_refresh

    def __call__(self, request: Request) -> None:
        """Refuse with 403 ``CSRF_CHECK_FAILED`` unless the request passes every check."""
        settings: Settings = request.app.state.settings
        allowed = settings.csrf_origins
        origin = request_origin(request.headers.get("origin"), request.headers.get("referer"))
        if request.headers.get("x-requested-with") == REQUESTED_WITH and origin in allowed:
            return
        metrics: Metrics | None = getattr(request.app.state, "metrics", None)
        if self.count_refresh and metrics is not None:
            metrics.auth_refresh_total.labels(outcome="csrf_refused").inc()
        logger.warning(
            "csrf check failed", extra={"event": "auth.csrf.refused", "route": self.route}
        )
        raise CsrfCheckFailed()
