"""Concurrent delivery of one webhook event through the real route (AC6.3.2, FR7.5).

The app here uses really-committing sessions on real PostgreSQL, so the two requests run in
separate transactions at the same time. The unique ``payment_events.provider_event_id``
decides: exactly one request processes the event, the other sees a duplicate, and exactly one
event record and one succeeded payment exist. Everything created is deleted afterwards.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.payments.fake_gateway import FakePaymentGateway
from app.payments.gateway import COMPLETED, CheckoutRequest
from app.payments.models import Payment, PaymentEvent, PaymentStatus
from app.platform.email.fake import RecordingEmailSender
from tests.helpers import make_settings
from tests.identity.conftest import TwoSessions, run_in_threads
from tests.payments.conftest import TEST_WEBHOOK_SECRET, insert_payment, post_webhook


@pytest.fixture
def committed_client(
    engine: Engine, committed_session_factory: Callable[[], Session]
) -> Iterator[tuple[TestClient, FakePaymentGateway]]:
    fake = FakePaymentGateway(webhook_secret=TEST_WEBHOOK_SECRET, base_url="http://testserver")
    app = create_app(
        make_settings(RATE_LIMIT_BACKEND="memory", FACE_MODEL_PRELOAD="false"),
        email_sender=RecordingEmailSender("test"),
        engine=engine,
        session_factory=committed_session_factory,
        payment_gateway=fake,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, fake


def test_two_concurrent_deliveries_of_one_event_record_one_payment(
    committed_client: tuple[TestClient, FakePaymentGateway],
    two_sessions: TwoSessions,
    committed_session_factory: Callable[[], Session],
) -> None:
    client, fake = committed_client
    user_id = two_sessions.make_user()
    with committed_session_factory() as session:
        payment = insert_payment(session, user_id, now=datetime.now(UTC))
        checkout = fake.create_checkout(
            CheckoutRequest(
                payment.id, user_id, 1999, "USD", "http://a.test", "http://b.test", "report"
            )
        )
        payment.provider_session_id = checkout.session_id
        session.commit()
    body, signature = fake.signed_event(checkout.session_id, COMPLETED)

    first, second = run_in_threads(
        lambda: post_webhook(client, body, signature),
        lambda: post_webhook(client, body, signature),
    )
    assert (first.status_code, second.status_code) == (200, 200)

    with committed_session_factory() as session:
        payments = list(session.scalars(select(Payment).where(Payment.user_id == user_id)))
        assert [p.status for p in payments] == [PaymentStatus.SUCCEEDED]
        events = session.scalar(
            select(func.count())
            .select_from(PaymentEvent)
            .where(PaymentEvent.payment_id == payments[0].id)
        )
        assert events == 1
    # Users are deleted by ``two_sessions``; payments and their events cascade.
