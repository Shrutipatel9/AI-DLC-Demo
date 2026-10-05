"""Per-IP limiter (NFR2.9, NFR11.2): PostgreSQL and in-memory adapters, client IP."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.platform.clock import FrozenClock
from app.platform.ratelimit import InMemoryRateLimiter, PostgresRateLimiter, client_ip
from app.platform.ratelimit_models import RateLimitHit


@pytest.fixture
def limiter_key(committed_session_factory: Callable[[], Session]) -> Iterator[str]:
    key = f"/auth/login:test-{uuid.uuid4().hex}"
    yield key
    with committed_session_factory() as session, session.begin():
        session.execute(delete(RateLimitHit).where(RateLimitHit.key.like(f"{key}%")))


@pytest.fixture
def pg_limiter(
    committed_session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> PostgresRateLimiter:
    return PostgresRateLimiter(committed_session_factory, frozen_clock, prune_probability=0.0)


def _count(factory: Callable[[], Session], key: str) -> int:
    with factory() as session:
        return int(session.scalar(select(func.count()).where(RateLimitHit.key == key)) or 0)


def test_twenty_first_request_is_refused_and_counted(
    pg_limiter: PostgresRateLimiter,
    limiter_key: str,
    committed_session_factory: Callable[[], Session],
    frozen_clock: FrozenClock,
) -> None:
    decisions = []
    for _ in range(21):
        decisions.append(pg_limiter.check_and_record(limiter_key, 20, 60))
        frozen_clock.advance(seconds=1)
    assert all(d.allowed for d in decisions[:20])
    assert not decisions[20].allowed
    # The oldest hit was at t=0 and leaves the window at t=60; now t=20.
    assert decisions[20].retry_after == 40
    assert _count(committed_session_factory, limiter_key) == 21


def test_window_slides_and_other_keys_are_independent(
    pg_limiter: PostgresRateLimiter, limiter_key: str, frozen_clock: FrozenClock
) -> None:
    for _ in range(3):
        pg_limiter.check_and_record(limiter_key, 3, 60)
    assert not pg_limiter.check_and_record(limiter_key, 3, 60).allowed
    assert pg_limiter.check_and_record(limiter_key + "-other-ip", 3, 60).allowed
    frozen_clock.advance(seconds=61)
    assert pg_limiter.check_and_record(limiter_key, 3, 60).allowed


def test_a_rolled_back_request_still_counts(
    pg_limiter: PostgresRateLimiter,
    limiter_key: str,
    committed_session_factory: Callable[[], Session],
) -> None:
    request_session = committed_session_factory()
    try:
        request_session.execute(text("SELECT 1"))
        pg_limiter.check_and_record(limiter_key, 20, 60)  # own short transaction
        request_session.rollback()  # the request's own work is undone
    finally:
        request_session.close()
    assert _count(committed_session_factory, limiter_key) == 1


def test_prune_removes_hits_older_than_two_hours(
    committed_session_factory: Callable[[], Session],
    limiter_key: str,
    frozen_clock: FrozenClock,
) -> None:
    limiter = PostgresRateLimiter(committed_session_factory, frozen_clock, prune_probability=1.0)
    old = PostgresRateLimiter(
        committed_session_factory,
        FrozenClock(frozen_clock.now() - timedelta(hours=3)),
        prune_probability=0.0,
    )
    old.check_and_record(limiter_key, 20, 60)
    limiter.check_and_record(limiter_key, 20, 60)
    assert _count(committed_session_factory, limiter_key) == 1


def test_in_memory_adapter_has_the_same_rules(frozen_clock: FrozenClock) -> None:
    limiter = InMemoryRateLimiter(frozen_clock)
    assert [limiter.check_and_record("k", 2, 10).allowed for _ in range(3)] == [True, True, False]
    refused = limiter.check_and_record("k", 2, 10)
    assert refused.retry_after == 10
    assert limiter.check_and_record("other", 2, 10).allowed
    frozen_clock.advance(seconds=11)
    assert limiter.check_and_record("k", 2, 10).allowed


@pytest.mark.parametrize(
    ("peer", "forwarded", "trusted", "expected"),
    [
        ("203.0.113.7", "198.51.100.1", [], "203.0.113.7"),  # no trusted proxies: peer wins
        ("10.0.0.5", "198.51.100.1, 10.0.0.9", ["10.0.0.0/8"], "198.51.100.1"),
        ("203.0.113.7", "198.51.100.1", ["10.0.0.0/8"], "203.0.113.7"),  # untrusted peer
        ("10.0.0.5", "10.0.0.6", ["10.0.0.0/8"], "10.0.0.5"),  # all hops trusted
        (None, None, [], "unknown"),
    ],
)
def test_client_ip(
    peer: str | None, forwarded: str | None, trusted: list[str], expected: str
) -> None:
    assert client_ip(peer, forwarded, trusted) == expected
