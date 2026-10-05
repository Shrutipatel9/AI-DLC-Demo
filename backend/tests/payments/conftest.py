"""Payment test fixtures: the real app on real PostgreSQL with the Stripe FAKE (never Stripe).

The app under test gets a :class:`FakePaymentGateway` whose deliverer only records the signed
webhook events; tests post them to ``/payments/stripe/webhook`` themselves, so every step is
deterministic. Photo sets come from the U4 fixtures and helpers (real MediaPipe model).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.main import create_app
from app.payments.fake_gateway import FakePaymentGateway
from app.payments.models import Payment, PaymentStatus
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from tests.faces import A_FRONT, A_LEFT, A_RIGHT
from tests.factories import SignedInUser
from tests.helpers import make_settings
from tests.identity.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    bearer,
    client,
    email_fake,
    two_sessions,
)
from tests.onboarding.conftest import seed_definition  # noqa: F401  (pytest fixture)
from tests.photos.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    media_root,
    settings_overrides,
    submitted,
    upload,
)

#: The webhook signing secret of the test fake (never a real secret).
TEST_WEBHOOK_SECRET = "whsec_test_payments_fixture"
WEBHOOK = "/payments/stripe/webhook"


@dataclass
class RecordedWebhooks:
    """Signed events the fake would have posted: ``(raw_body, signature)``."""

    events: list[tuple[bytes, str]] = field(default_factory=list)

    def __call__(self, raw_body: bytes, signature: str) -> None:
        self.events.append((raw_body, signature))


@pytest.fixture
def webhooks() -> RecordedWebhooks:
    """The fake's recording deliverer."""
    return RecordedWebhooks()


@pytest.fixture
def fake_gateway(webhooks: RecordedWebhooks) -> FakePaymentGateway:
    """The Stripe fake used by the app under test."""
    return FakePaymentGateway(
        webhook_secret=TEST_WEBHOOK_SECRET, base_url="http://testserver", deliver=webhooks
    )


@pytest.fixture
def app(
    settings_overrides: dict[str, Any],  # noqa: F811
    frozen_clock: FrozenClock,
    email_fake: RecordingEmailSender,  # noqa: F811
    engine: Engine,
    session_factory: Callable[[], Session],
    fake_gateway: FakePaymentGateway,
) -> FastAPI:
    """The real API app with the payment fake injected (PostgreSQL limiter, rolled back)."""
    settings = make_settings(RATE_LIMIT_BACKEND="postgres", **settings_overrides)
    return create_app(
        settings,
        clock=frozen_clock,
        email_sender=email_fake,
        engine=engine,
        session_factory=session_factory,
        payment_gateway=fake_gateway,
    )


def upload_consistent_set(api: TestClient, user: SignedInUser) -> None:
    """Upload the three same-person fixture photos (U4 fixtures, real model)."""
    for angle, name in (("front", A_FRONT), ("left_3q", A_LEFT), ("right_3q", A_RIGHT)):
        response = upload(api, user, angle, name)
        assert response.status_code == 200, response.text


@pytest.fixture
def consistent(client: TestClient, submitted: SignedInUser) -> SignedInUser:  # noqa: F811
    """A signed-in user with a complete, same-person photo set and no payment."""
    upload_consistent_set(client, submitted)
    return submitted


def checkout(api: TestClient, user: SignedInUser) -> Any:
    """``POST /payments/checkout`` as the web app does."""
    return api.post("/payments/checkout", headers=bearer(user.access_token))


def status(api: TestClient, user: SignedInUser) -> dict[str, Any]:
    """``GET /payments/status`` body (asserts 200 and no-store)."""
    response = api.get("/payments/status", headers=bearer(user.access_token))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body: dict[str, Any] = response.json()
    return body


def post_webhook(api: TestClient, raw_body: bytes, signature: str | None) -> Any:
    """Post a raw webhook body as Stripe would (no token, no CSRF headers)."""
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["Stripe-Signature"] = signature
    return api.post(WEBHOOK, content=raw_body, headers=headers)


def insert_payment(
    session: Session,
    user_id: str | uuid.UUID,
    *,
    now: datetime,
    status: PaymentStatus = PaymentStatus.PENDING,
    session_id: str | None = None,
    amount: int = 1999,
) -> Payment:
    """Insert a payment row directly (tests that do not need a real checkout)."""
    payment = Payment(
        id=uuid.uuid4(),
        user_id=uuid.UUID(str(user_id)),
        provider="fake",
        provider_session_id=session_id,
        amount=amount,
        currency="USD",
        status=status.value,
        created_at=now,
        updated_at=now,
        paid_at=now if status == PaymentStatus.SUCCEEDED else None,
    )
    session.add(payment)
    session.commit()
    return payment
