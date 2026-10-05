"""Per-IP sliding-window rate limiting (NFR2.9, NFR11.2, security design section 4).

- :class:`RateLimiter` is the port; adapters are :class:`PostgresRateLimiter` (default,
  shared across processes) and :class:`InMemoryRateLimiter` (development/tests).
- The PostgreSQL adapter uses its OWN short session, so a later rollback of the
  request cannot erase a hit. ``pg_advisory_xact_lock(hashtext(key))`` serialises
  requests for one key, so the limit cannot be overshot.
- Every request is recorded, including refused ones (the 21st request counts).
- About 1% of calls prune rows older than 2 hours (twice the longest window).
"""

from __future__ import annotations

import ipaddress
import logging
import math
import random
import threading
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol

from fastapi import Request
from sqlalchemy import delete, func, insert, select
from sqlalchemy.orm import Session

from app.platform.clock import Clock
from app.platform.errors import RateLimited
from app.platform.metrics import Metrics
from app.platform.ratelimit_models import RateLimitHit

logger = logging.getLogger("platform.ratelimit")

PRUNE_AGE = timedelta(hours=2)


@dataclass(frozen=True)
class Decision:
    """Outcome of one limiter check.

    Attributes:
        allowed: False when the limit was already reached before this request.
        retry_after: Seconds until the oldest hit leaves the window (0 when allowed).
        count: Hits in the window before this request.
    """

    allowed: bool
    retry_after: int
    count: int


class RateLimiter(Protocol):
    """Counts hits per key in a sliding window."""

    def check_and_record(self, key: str, limit: int, window_seconds: int) -> Decision:
        """Record a hit for ``key`` and say whether it is within ``limit``."""
        ...


def _decide(
    count: int, oldest: datetime | None, now: datetime, limit: int, window: int
) -> Decision:
    if count < limit or oldest is None:
        return Decision(allowed=True, retry_after=0, count=count)
    leaves_at = oldest + timedelta(seconds=window)
    wait = max(1, math.ceil((leaves_at - now).total_seconds()))
    return Decision(allowed=False, retry_after=wait, count=count)


class InMemoryRateLimiter:
    """Process-local limiter for development and tests (not shared across processes)."""

    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self._hits: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_record(self, key: str, limit: int, window_seconds: int) -> Decision:
        """Record a hit and decide."""
        now = self._clock.now()
        window_start = now - timedelta(seconds=window_seconds)
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= window_start:
                hits.popleft()
            decision = _decide(len(hits), hits[0] if hits else None, now, limit, window_seconds)
            hits.append(now)
        return decision


class PostgresRateLimiter:
    """PostgreSQL-backed limiter shared by every API process.

    Args:
        session_factory: Factory for the limiter's own short sessions.
        clock: Time source.
        prune_probability: Chance per call of deleting rows older than 2 hours.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        clock: Clock,
        *,
        prune_probability: float = 0.01,
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._prune_probability = prune_probability

    def check_and_record(self, key: str, limit: int, window_seconds: int) -> Decision:
        """Record a hit in its own committed transaction and decide."""
        now = self._clock.now()
        window_start = now - timedelta(seconds=window_seconds)
        with self._session_factory() as session, session.begin():
            session.execute(select(func.pg_advisory_xact_lock(func.hashtext(key))))
            count, oldest = session.execute(
                select(func.count(), func.min(RateLimitHit.hit_at)).where(
                    RateLimitHit.key == key, RateLimitHit.hit_at > window_start
                )
            ).one()
            session.execute(insert(RateLimitHit).values(key=key, hit_at=now))
            if random.random() < self._prune_probability:  # noqa: S311  (not security)
                self.prune(session, now)
        return _decide(int(count), oldest, now, limit, window_seconds)

    @staticmethod
    def prune(session: Session, now: datetime) -> int:
        """Delete hits older than 2 hours. Returns the number of rows removed."""
        result = session.execute(delete(RateLimitHit).where(RateLimitHit.hit_at < now - PRUNE_AGE))
        return int(getattr(result, "rowcount", 0) or 0)


def client_ip(peer: str | None, forwarded_for: str | None, trusted_proxies: Sequence[str]) -> str:
    """Return the client address used as the limiter key.

    The socket peer is used unless it is a trusted proxy; then ``X-Forwarded-For`` is
    walked from the right and the first address that is not a trusted proxy is taken.
    """
    if not peer:
        return "unknown"
    networks = [ipaddress.ip_network(entry, strict=False) for entry in trusted_proxies]

    def is_trusted(address: str) -> bool:
        try:
            parsed = ipaddress.ip_address(address)
        except ValueError:
            return False
        return any(parsed in network for network in networks)

    if not networks or not is_trusted(peer) or not forwarded_for:
        return peer
    hops: Iterable[str] = reversed([hop.strip() for hop in forwarded_for.split(",") if hop.strip()])
    for hop in hops:
        if not is_trusted(hop):
            return hop
    return peer


LimitKind = Literal["auth", "refresh"]


class PerIpLimit:
    """FastAPI dependency enforcing the per-IP limit on one route.

    It is a sync dependency, so FastAPI runs the database work in its thread pool.

    Args:
        route: Route template; part of the limiter key (limits are per route and IP).
        kind: ``auth`` uses ``AUTH_RATE_LIMIT_PER_MINUTE``; ``refresh`` (``/auth/refresh``
            and ``/auth/logout``) uses the higher ``REFRESH_RATE_LIMIT_PER_MINUTE`` (U2).
    """

    def __init__(self, route: str, *, kind: LimitKind = "auth") -> None:
        self.route = route
        self.kind = kind

    def __call__(self, request: Request) -> None:
        """Record the hit and refuse with 429 ``RATE_LIMITED`` over the limit."""
        state = request.app.state
        settings = state.settings
        limiter: RateLimiter = state.rate_limiter
        peer = request.client.host if request.client else None
        ip = client_ip(peer, request.headers.get("x-forwarded-for"), settings.trusted_proxies)
        limit = (
            settings.refresh_rate_limit_per_window
            if self.kind == "refresh"
            else settings.auth_rate_limit_per_window
        )
        decision = limiter.check_and_record(
            f"{self.route}:{ip}", limit, settings.auth_rate_limit_window_seconds
        )
        if not decision.allowed:
            metrics: Metrics | None = getattr(state, "metrics", None)
            if metrics is not None:
                metrics.rate_limited_total.labels(route=self.route).inc()
            logger.warning(
                "request rate limited", extra={"event": "auth.rate_limited", "route": self.route}
            )
            raise RateLimited(retry_after=decision.retry_after)
