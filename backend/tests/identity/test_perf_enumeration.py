"""Anti-enumeration timing (NFR2.11; NFR requirements post-review R-06; NFD post-review R-03).
Marker ``perf``.

``POST /auth/password/forgot`` must take the same time whatever the email: a real eligible
account, an unknown email, an account in cooldown, and a locked account. 200 samples per
branch, interleaved, after a warm-up. Both the median and the p95 of every branch must be
within 50 ms of every other branch.

The email itself is issued and sent by a background task **after** the response, so it
is not part of the response time. The in-process test client only returns once background
tasks finish, so the task is replaced by a recorder here; the recorder also proves the
"real" samples really took the sending branch and the others did not.
"""

from __future__ import annotations

import statistics
import time
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.identity.delivery import PendingCode
from app.identity.models import CodePurpose, VerificationAttemptCounter
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from tests.conftest import PERF_RESULTS
from tests.factories import unique_email, verified_user

pytestmark = pytest.mark.perf

SAMPLES = 200
WARMUP = 10
MAX_DIFF_MS = 50.0


@pytest.fixture
def settings_overrides() -> dict[str, Any]:
    return {"AUTH_RATE_LIMIT_PER_MINUTE": 100_000}


def _p95(values: list[float]) -> float:
    return statistics.quantiles(values, n=20)[18]


def test_forgot_password_takes_the_same_time_for_every_branch(
    app: FastAPI,
    client: TestClient,
    email_fake: RecordingEmailSender,
    frozen_clock: FrozenClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delivered: list[PendingCode] = []

    async def record(pending: PendingCode) -> None:
        delivered.append(pending)

    monkeypatch.setattr(app.state.identity.delivery, "deliver", record)
    real = verified_user(client, email_fake)
    cooling = verified_user(client, email_fake)
    locked = verified_user(client, email_fake)
    locked_id = locked.user_id

    def lock_account() -> None:
        with app.state.session_factory() as session:
            client.post("/auth/password/forgot", json={"email": locked.email})
            session.execute(
                update(VerificationAttemptCounter)
                .where(
                    VerificationAttemptCounter.user_id == locked_id,
                    VerificationAttemptCounter.purpose == CodePurpose.PASSWORD_RESET.value,
                )
                .values(failed_count=5, locked_until=frozen_clock.now() + timedelta(minutes=15))
            )
            session.commit()

    def timed(email: str) -> float:
        started = time.perf_counter()
        response = client.post("/auth/password/forgot", json={"email": email})
        elapsed = (time.perf_counter() - started) * 1000
        assert response.status_code == 202
        return elapsed

    timings: dict[str, list[float]] = {"real": [], "unknown": [], "cooldown": [], "locked": []}
    for round_index in range(WARMUP + SAMPLES):
        frozen_clock.advance(seconds=61)  # the real account is eligible again
        lock_account()
        client.post("/auth/password/forgot", json={"email": cooling.email})  # starts cooldown
        sent_before = len(delivered)
        samples = {
            "real": timed(real.email),
            "unknown": timed(unique_email("ghost")),
            "cooldown": timed(cooling.email),
            "locked": timed(locked.email),
        }
        assert [p.email for p in delivered[sent_before:]] == [real.email]
        if round_index >= WARMUP:
            for branch, value in samples.items():
                timings[branch].append(value)

    medians = {branch: statistics.median(values) for branch, values in timings.items()}
    p95s = {branch: _p95(values) for branch, values in timings.items()}
    median_spread = max(medians.values()) - min(medians.values())
    p95_spread = max(p95s.values()) - min(p95s.values())
    summary = ", ".join(
        f"{branch} median={medians[branch]:.1f} p95={p95s[branch]:.1f}" for branch in timings
    )
    PERF_RESULTS.append(
        f"forgot-password timing ({SAMPLES} samples/branch): {summary}; "
        f"median spread={median_spread:.1f} ms, p95 spread={p95_spread:.1f} ms (target < 50 ms)"
    )
    assert median_spread < MAX_DIFF_MS, summary
    assert p95_spread < MAX_DIFF_MS, summary
