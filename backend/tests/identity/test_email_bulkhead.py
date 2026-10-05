"""Email bulkhead (NFR5.13, reliability design section 2, plan decision D6).

With 10 slow sends in flight, ``/auth/me`` must still answer within its target. This test
uses real commits (concurrent requests need separate connections) and cleans up after
itself.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import anyio
import httpx
import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.identity.models import User
from app.main import create_app
from app.platform.email.fake import RecordingEmailSender
from tests.factories import VALID_PASSWORD
from tests.helpers import make_settings

PREFIX = "bulkhead-"


@pytest.fixture
def cleanup(committed_session_factory: Callable[[], Session]) -> Iterator[None]:
    yield
    with committed_session_factory() as session:
        session.execute(delete(User).where(User.email.like(f"{PREFIX}%")))
        session.commit()


def test_me_answers_while_ten_slow_sends_are_in_flight(engine: Engine, cleanup: None) -> None:
    fake = RecordingEmailSender("test")
    settings = make_settings(
        RATE_LIMIT_BACKEND="memory",
        EMAIL_MAX_CONCURRENCY="10",
        EMAIL_SEND_BUDGET_SECONDS="25",
    )
    app = create_app(settings, email_sender=fake, engine=engine)
    dispatcher = app.state.email_dispatcher
    me_latency: list[float] = []

    async def scenario() -> None:
        dispatcher.start()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            email = f"{PREFIX}{time.time_ns()}@example.test"
            body = {"fullName": "Bulk Head", "email": email, "password": VALID_PASSWORD}
            assert (await client.post("/auth/register", json=body)).status_code == 202
            verify = {"email": email, "code": fake.last_code_for(email), "purpose": "signup"}
            token = (await client.post("/auth/verify", json=verify)).json()["accessToken"]

            fake.delay_seconds = 3.0

            async def slow_signup(index: int) -> None:
                payload = {
                    "fullName": "Slow",
                    "email": f"{PREFIX}{index}-{time.time_ns()}@example.test",
                    "password": VALID_PASSWORD,
                }
                await client.post("/auth/register", json=payload)

            async with anyio.create_task_group() as group:
                for index in range(10):
                    group.start_soon(slow_signup, index)
                with anyio.fail_after(10):
                    while dispatcher.in_flight < 10:  # noqa: ASYNC110  (polls a counter, no event to wait on)
                        await anyio.sleep(0.05)
                started = time.perf_counter()
                response = await client.get(
                    "/auth/me", headers={"Authorization": f"Bearer {token}"}
                )
                me_latency.append(time.perf_counter() - started)
                assert response.status_code == 200
                assert dispatcher.in_flight == 10

    anyio.run(scenario)
    assert me_latency[0] < 0.5
