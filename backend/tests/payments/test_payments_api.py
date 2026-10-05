"""``/payments`` API and webhook with real PostgreSQL, the real photo check and the Stripe fake.

Contract C1 ``/payments``, contract C2 webhook; US6.1-US6.5. The photo sets go through the
real MediaPipe model (U4 fixtures), so the 409 bodies are the U4 function's own results.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.main import create_app
from app.payments.fake_gateway import FakePaymentGateway
from app.payments.models import Payment, PaymentEvent, PaymentStatus
from app.photos.public import PhotoIntakeService, check_identity
from app.platform.clock import FrozenClock
from app.platform.email.fake import RecordingEmailSender
from tests.faces import B_LEFT
from tests.factories import SignedInUser, verified_user
from tests.helpers import make_settings
from tests.payments.conftest import (
    TEST_WEBHOOK_SECRET,
    RecordedWebhooks,
    bearer,
    checkout,
    insert_payment,
    post_webhook,
    status,
    upload,
    upload_consistent_set,
)


def fake_session_id(body: dict[str, Any]) -> str:
    url: str = body["checkoutUrl"]
    assert url.startswith("http://testserver/payments/fake-checkout/cs_fake_")
    return url.rsplit("/", 1)[1]


# --- Offer (US6.1) ---------------------------------------------------------------------------


def test_the_offer_is_the_configured_price_and_what_it_unlocks(
    client: TestClient, submitted: SignedInUser
) -> None:
    response = client.get("/payments/offer", headers=bearer(submitted.access_token))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert (body["amount"], body["currency"]) == (1999, "USD")  # tests.helpers.base_env
    assert len(body["includes"]) == 3
    assert any("11 features" in item for item in body["includes"])


def test_payment_routes_need_a_signed_in_user(client: TestClient) -> None:
    assert client.get("/payments/offer").status_code == 401
    assert client.post("/payments/checkout").status_code == 401
    assert client.get("/payments/status").status_code == 401


def test_the_price_comes_from_configuration(
    engine: Engine,
    session_factory: Callable[[], Session],
    frozen_clock: FrozenClock,
    settings_overrides: dict[str, Any],
    email_fake: RecordingEmailSender,
    seed_definition: Any,
) -> None:
    """AC6.1.3: a changed price reaches the screen and the next checkout session."""
    from tests.photos.conftest import submitted_user_for

    fake = FakePaymentGateway(webhook_secret=TEST_WEBHOOK_SECRET, base_url="http://testserver")
    app = create_app(
        make_settings(
            REPORT_PRICE_AMOUNT="4500", REPORT_PRICE_CURRENCY="eur", **settings_overrides
        ),
        clock=frozen_clock,
        email_sender=email_fake,
        engine=engine,
        session_factory=session_factory,
        payment_gateway=fake,
    )
    with TestClient(app) as api:
        user = submitted_user_for(api, email_fake, seed_definition)
        offer = api.get("/payments/offer", headers=bearer(user.access_token)).json()
        assert (offer["amount"], offer["currency"]) == (4500, "EUR")
        upload_consistent_set(api, user)
        assert checkout(api, user).status_code == 201
    [session] = fake.sessions
    assert (session.request.amount, session.request.currency) == (4500, "EUR")


# --- Checkout (US6.2) -------------------------------------------------------------------------


def test_checkout_returns_the_hosted_checkout_url_for_a_consistent_set(
    client: TestClient,
    consistent: SignedInUser,
    fake_gateway: FakePaymentGateway,
    db_session: Session,
) -> None:
    response = checkout(client, consistent)
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    session_id = fake_session_id(response.json())
    recorded = fake_gateway.session(session_id)
    assert recorded is not None
    assert (recorded.request.amount, recorded.request.currency) == (1999, "USD")
    assert recorded.request.success_url == "http://localhost:3000/payment/success"
    assert recorded.request.cancel_url == "http://localhost:3000/payment/cancel"
    payment = db_session.scalars(
        select(Payment).where(Payment.user_id == uuid.UUID(consistent.user_id))
    ).one()
    assert (payment.status, payment.provider_session_id) == ("pending", session_id)
    assert status(client, consistent)["state"] == "pending"


def test_checkout_with_missing_photos_is_409_incomplete(
    client: TestClient, submitted: SignedInUser
) -> None:
    response = checkout(client, submitted)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PHOTO_SET_INCOMPLETE"


def test_checkout_with_a_mismatched_set_returns_the_same_angles_as_the_u4_check(
    app: FastAPI, client: TestClient, submitted: SignedInUser, db_session: Session
) -> None:
    """AC6.2.2: the 409 details equal the US5.6 function's result for the same photos."""
    upload_consistent_set(client, submitted)
    assert upload(client, submitted, "left_3q", B_LEFT).status_code == 200

    response = checkout(client, submitted)
    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "PHOTO_IDENTITY_MISMATCH"
    photos: PhotoIntakeService = app.state.photos
    expected = check_identity(photos, db_session, uuid.UUID(submitted.user_id))
    assert expected.status == "mismatch"
    assert [d["angle"] for d in error["details"]] == list(expected.mismatched_angles)
    assert db_session.scalar(select(func.count()).select_from(Payment)) == 0


# --- Webhook, status and confirmation (US6.3, US6.5) ---------------------------------------


def test_pay_on_the_fake_page_then_the_webhook_confirms_the_payment(
    client: TestClient,
    consistent: SignedInUser,
    fake_gateway: FakePaymentGateway,
    webhooks: RecordedWebhooks,
) -> None:
    session_id = fake_session_id(checkout(client, consistent).json())

    page = client.get(f"/payments/fake-checkout/{session_id}")
    assert page.status_code == 200
    assert 'data-testid="fake-checkout-pay"' in page.text
    assert "19.99 USD" in page.text

    paid = client.post(f"/payments/fake-checkout/{session_id}/pay", follow_redirects=False)
    assert paid.status_code == 303
    assert paid.headers["location"] == "http://localhost:3000/payment/success"
    # Back on the success page before the webhook: still pending (AC6.5.1).
    before = status(client, consistent)
    assert (before["state"], before["paidAt"]) == ("pending", None)
    assert before["confirmWaitSeconds"] == 30

    [(body, signature)] = webhooks.events
    response = post_webhook(client, body, signature)
    assert response.status_code == 200
    assert response.json() == {"received": True}
    after = status(client, consistent)
    assert after["state"] == "paid"
    assert after["paidAt"] is not None

    again = checkout(client, consistent)
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ALREADY_PAID"


def test_cancel_on_the_fake_page_returns_with_nothing_charged(
    client: TestClient, consistent: SignedInUser, webhooks: RecordedWebhooks
) -> None:
    session_id = fake_session_id(checkout(client, consistent).json())
    response = client.post(f"/payments/fake-checkout/{session_id}/cancel", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "http://localhost:3000/payment/cancel"
    assert webhooks.events == []
    assert status(client, consistent)["state"] == "pending"  # never paid
    assert checkout(client, consistent).status_code == 201  # a new attempt is allowed


def test_a_duplicate_webhook_records_one_event(
    client: TestClient, consistent: SignedInUser, webhooks: RecordedWebhooks, db_session: Session
) -> None:
    session_id = fake_session_id(checkout(client, consistent).json())
    client.post(f"/payments/fake-checkout/{session_id}/pay", follow_redirects=False)
    [(body, signature)] = webhooks.events
    assert post_webhook(client, body, signature).status_code == 200
    assert post_webhook(client, body, signature).status_code == 200  # Stripe retry: still 200
    assert db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 1
    payments = list(db_session.scalars(select(Payment)))
    assert [p.status for p in payments] == [PaymentStatus.SUCCEEDED]


def test_a_webhook_with_a_bad_or_missing_signature_is_400_and_changes_nothing(
    client: TestClient,
    email_fake: RecordingEmailSender,
    fake_gateway: FakePaymentGateway,
    db_session: Session,
    frozen_clock: FrozenClock,
) -> None:
    """AC6.3.3."""
    user = verified_user(client, email_fake)
    stored = insert_payment(db_session, user.user_id, now=frozen_clock.now())
    from app.payments.gateway import COMPLETED, CheckoutRequest

    session = fake_gateway.create_checkout(
        CheckoutRequest(stored.id, stored.user_id, 1999, "USD", "http://a.t", "http://b.t", "r")
    )
    stored.provider_session_id = session.session_id
    db_session.commit()
    body, signature = fake_gateway.signed_event(session.session_id, COMPLETED)

    tampered = body.replace(b'"paid"', b'"PAID"')
    for raw, sig in ((tampered, signature), (body, None), (body, "t=1,v1=00")):
        response = post_webhook(client, raw, sig)
        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_FAILED"
        assert error["details"][0]["reason"] == "SIGNATURE_INVALID"
    db_session.refresh(stored)
    assert stored.status == PaymentStatus.PENDING
    assert db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 0
    assert status(client, user)["state"] == "pending"


def test_status_is_none_without_any_payment(client: TestClient, submitted: SignedInUser) -> None:
    body = status(client, submitted)
    assert body == {"state": "none", "paidAt": None, "confirmWaitSeconds": 30}


def test_an_oversized_webhook_body_is_refused_before_parsing(client: TestClient) -> None:
    response = post_webhook(client, b"{" + b" " * (300 * 1024) + b"}", "t=1,v1=00")
    assert response.status_code == 413
    assert response.json()["error"]["details"][0]["reason"] == "BODY_TOO_LARGE"


# --- The fake's hosted page ------------------------------------------------------------------


def test_the_fake_page_refuses_unknown_and_malformed_sessions(client: TestClient) -> None:
    unknown = "cs_fake_" + "0" * 24
    assert client.get(f"/payments/fake-checkout/{unknown}").status_code == 404
    assert client.post(f"/payments/fake-checkout/{unknown}/pay").status_code == 404
    assert client.post(f"/payments/fake-checkout/{unknown}/cancel").status_code == 404
    assert client.get("/payments/fake-checkout/not-a-session").status_code == 422


def test_the_fake_page_does_not_exist_with_the_stripe_provider(
    engine: Engine, session_factory: Callable[[], Session], frozen_clock: FrozenClock
) -> None:
    app = create_app(
        make_settings(
            PAYMENT_PROVIDER="stripe",
            STRIPE_SECRET_KEY="sk_test_unused",  # never used: no checkout is made
            STRIPE_WEBHOOK_SECRET="whsec_placeholder",
            FACE_MODEL_PRELOAD="false",
        ),
        clock=frozen_clock,
        email_sender=RecordingEmailSender("test"),
        engine=engine,
        session_factory=session_factory,
    )
    with TestClient(app) as api:
        assert api.get("/payments/fake-checkout/cs_fake_" + "0" * 24).status_code == 404
        # The webhook is public and verified with the Stripe secret.
        assert post_webhook(api, b"{}", "t=1,v1=00").status_code == 400


def test_the_fake_page_answers_404_when_another_gateway_is_wired(
    app: FastAPI, client: TestClient
) -> None:
    app.state.payment_gateway = object()  # as if the provider were not the fake
    assert client.get("/payments/fake-checkout/cs_fake_" + "0" * 24).status_code == 404
