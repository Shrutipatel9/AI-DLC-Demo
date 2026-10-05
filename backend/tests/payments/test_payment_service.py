"""PaymentService on real PostgreSQL with the Stripe fake and a stub same-person check.

US6.2-US6.4; FR7.4-FR7.6. The checkout's photo check uses the real U4 function in
``test_payments_api.py``; here a stub returns fixed results so each rule is isolated.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.identity.models import User
from app.payments.fake_gateway import FakePaymentGateway
from app.payments.gateway import (
    ASYNC_FAILED,
    ASYNC_SUCCEEDED,
    COMPLETED,
    EXPIRED,
    CheckoutRequest,
    CheckoutSession,
    GatewayError,
    WebhookEvent,
)
from app.payments.models import Payment, PaymentEvent, PaymentStatus
from app.payments.public import paid_photo_snapshot
from app.payments.services import OFFER_INCLUDES, PaymentService, Price
from app.photos.public import IdentityResult
from app.platform.clock import FrozenClock
from app.platform.errors import (
    AlreadyPaid,
    PaymentRequired,
    PhotoIdentityMismatch,
    PhotoSetIncomplete,
    UpstreamTimeout,
    UpstreamUnavailable,
    WebhookRejected,
)
from tests.payments.conftest import TEST_WEBHOOK_SECRET, RecordedWebhooks, insert_payment

CONSISTENT = IdentityResult(status="consistent", mismatched_angles=())


def make_user(session: Session) -> uuid.UUID:
    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        full_name="Pay Test",
        email=f"pay-{uuid.uuid4().hex[:8]}@example.test",
        password_hash="not-a-real-hash",
        is_verified=True,
        role="user",
        created_at=now,
        updated_at=now,
        verified_at=now,
    )
    session.add(user)
    session.commit()
    return user.id


class Identity:
    """A stub same-person check returning ``result`` and counting calls."""

    def __init__(self, result: IdentityResult = CONSISTENT) -> None:
        self.result = result
        self.calls = 0

    def __call__(self, _session: Session, _user_id: uuid.UUID) -> IdentityResult:
        self.calls += 1
        return self.result


class FailingGateway(FakePaymentGateway):
    """A fake whose checkout fails like an unreachable Stripe."""

    def __init__(self, *, timeout: bool) -> None:
        super().__init__(webhook_secret=TEST_WEBHOOK_SECRET, base_url="http://testserver")
        self.timeout = timeout

    def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        raise GatewayError("down", timeout=self.timeout)


@pytest.fixture
def recorder() -> RecordedWebhooks:
    return RecordedWebhooks()


@pytest.fixture
def fake(recorder: RecordedWebhooks) -> FakePaymentGateway:
    return FakePaymentGateway(
        webhook_secret=TEST_WEBHOOK_SECRET, base_url="http://testserver", deliver=recorder
    )


def service(
    gateway: FakePaymentGateway, clock: FrozenClock, identity: Identity | None = None
) -> PaymentService:
    return PaymentService(
        gateway=gateway,
        clock=clock,
        identity_check=identity or Identity(),
        price=Price(2900, "EUR"),
        success_url="http://web.test/payment/success",
        cancel_url="http://web.test/payment/cancel",
        confirm_wait_seconds=30,
    )


def payments_of(session: Session, user_id: uuid.UUID) -> list[Payment]:
    return list(session.scalars(select(Payment).where(Payment.user_id == user_id)))


# --- Offer and checkout (US6.1, US6.2) -----------------------------------------------------


def test_the_offer_is_the_configured_price(
    fake: FakePaymentGateway, frozen_clock: FrozenClock
) -> None:
    offer = service(fake, frozen_clock).offer()
    assert (offer.amount, offer.currency) == (2900, "EUR")
    assert offer.includes == OFFER_INCLUDES
    assert len(offer.includes) == 3


def test_checkout_records_a_pending_payment_at_the_configured_price(
    db_session: Session, fake: FakePaymentGateway, frozen_clock: FrozenClock
) -> None:
    user_id = make_user(db_session)
    identity = Identity()
    checkout = service(fake, frozen_clock, identity).start_checkout(db_session, user_id)

    assert identity.calls == 1  # the same-person re-check runs at checkout (BR-005)
    [payment] = payments_of(db_session, user_id)
    assert payment.status == PaymentStatus.PENDING
    assert (payment.amount, payment.currency, payment.provider) == (2900, "EUR", "fake")
    assert payment.provider_session_id == checkout.session_id
    recorded = fake.session(checkout.session_id)
    assert recorded is not None
    assert (recorded.request.amount, recorded.request.currency) == (2900, "EUR")
    assert recorded.request.payment_id == payment.id
    assert recorded.request.success_url == "http://web.test/payment/success"


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (IdentityResult(status="incomplete", mismatched_angles=()), PhotoSetIncomplete),
        (IdentityResult(status="mismatch", mismatched_angles=("right_3q",)), PhotoIdentityMismatch),
    ],
)
def test_checkout_needs_a_complete_consistent_photo_set(
    db_session: Session,
    fake: FakePaymentGateway,
    frozen_clock: FrozenClock,
    result: IdentityResult,
    error: type[Exception],
) -> None:
    user_id = make_user(db_session)
    with pytest.raises(error) as caught:
        service(fake, frozen_clock, Identity(result)).start_checkout(db_session, user_id)
    if isinstance(caught.value, PhotoIdentityMismatch):
        assert caught.value.mismatched_angles == ["right_3q"]
    assert payments_of(db_session, user_id) == []
    assert fake.sessions == []  # the provider is never called


def test_checkout_after_a_successful_payment_is_already_paid(
    db_session: Session, fake: FakePaymentGateway, frozen_clock: FrozenClock
) -> None:
    user_id = make_user(db_session)
    insert_payment(db_session, user_id, now=frozen_clock.now(), status=PaymentStatus.SUCCEEDED)
    identity = Identity()
    with pytest.raises(AlreadyPaid):
        service(fake, frozen_clock, identity).start_checkout(db_session, user_id)
    assert identity.calls == 0


@pytest.mark.parametrize(
    ("timeout", "error"), [(False, UpstreamUnavailable), (True, UpstreamTimeout)]
)
def test_a_provider_failure_marks_the_attempt_failed_and_charges_nothing(
    db_session: Session, frozen_clock: FrozenClock, timeout: bool, error: type[Exception]
) -> None:
    user_id = make_user(db_session)
    payments = service(FailingGateway(timeout=timeout), frozen_clock)
    with pytest.raises(error, match="not been charged"):
        payments.start_checkout(db_session, user_id)
    [payment] = payments_of(db_session, user_id)
    assert payment.status == PaymentStatus.FAILED
    assert payments.status(db_session, user_id).state == "none"


# --- Webhook (US6.3) -------------------------------------------------------------------------


def paid_checkout(
    db_session: Session, payments: PaymentService, fake: FakePaymentGateway, user_id: uuid.UUID
) -> CheckoutSession:
    checkout = payments.start_checkout(db_session, user_id)
    fake.pay(checkout.session_id)
    return checkout


def test_a_valid_success_webhook_marks_the_payment_succeeded(
    db_session: Session,
    fake: FakePaymentGateway,
    recorder: RecordedWebhooks,
    frozen_clock: FrozenClock,
) -> None:
    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    paid_checkout(db_session, payments, fake, user_id)
    assert payments.status(db_session, user_id).state == "pending"  # not before the webhook

    frozen_clock.advance(timedelta(seconds=5))
    body, signature = recorder.events[0]
    assert payments.handle_webhook(db_session, body, signature) == "processed"

    [payment] = payments_of(db_session, user_id)
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.paid_at == frozen_clock.now()
    view = payments.status(db_session, user_id)
    assert (view.state, view.paid_at) == ("paid", frozen_clock.now())
    assert payments.require_paid(db_session, user_id).payment_id == payment.id


def test_the_same_event_twice_changes_nothing_the_second_time(
    db_session: Session,
    fake: FakePaymentGateway,
    recorder: RecordedWebhooks,
    frozen_clock: FrozenClock,
) -> None:
    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    paid_checkout(db_session, payments, fake, user_id)
    body, signature = recorder.events[0]
    assert payments.handle_webhook(db_session, body, signature) == "processed"
    first_paid_at = payments_of(db_session, user_id)[0].paid_at
    frozen_clock.advance(timedelta(minutes=1))
    assert payments.handle_webhook(db_session, body, signature) == "duplicate"

    assert len(payments_of(db_session, user_id)) == 1
    assert payments_of(db_session, user_id)[0].paid_at == first_paid_at
    events = db_session.scalar(select(func.count()).select_from(PaymentEvent))
    assert events == 1


def test_a_bad_signature_is_rejected_and_nothing_changes(
    db_session: Session,
    fake: FakePaymentGateway,
    recorder: RecordedWebhooks,
    frozen_clock: FrozenClock,
) -> None:
    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    paid_checkout(db_session, payments, fake, user_id)
    body, _signature = recorder.events[0]
    with pytest.raises(WebhookRejected) as caught:
        payments.handle_webhook(db_session, body, "t=1,v1=" + "0" * 64)
    assert caught.value.reason == "SIGNATURE_INVALID"
    assert payments_of(db_session, user_id)[0].status == PaymentStatus.PENDING
    assert db_session.scalar(select(func.count()).select_from(PaymentEvent)) == 0


def test_unpaid_completion_waits_and_async_success_confirms(
    db_session: Session, fake: FakePaymentGateway, frozen_clock: FrozenClock
) -> None:
    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    checkout = payments.start_checkout(db_session, user_id)
    body, sig = fake.signed_event(checkout.session_id, COMPLETED, payment_status="unpaid")
    assert payments.handle_webhook(db_session, body, sig) == "processed"
    assert payments.status(db_session, user_id).state == "pending"

    body, sig = fake.signed_event(checkout.session_id, ASYNC_SUCCEEDED)
    payments.handle_webhook(db_session, body, sig)
    assert payments.status(db_session, user_id).state == "paid"


@pytest.mark.parametrize("event_type", [EXPIRED, ASYNC_FAILED])
def test_an_expired_or_failed_session_marks_a_pending_payment_failed(
    db_session: Session, fake: FakePaymentGateway, frozen_clock: FrozenClock, event_type: str
) -> None:
    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    checkout = payments.start_checkout(db_session, user_id)
    body, sig = fake.signed_event(checkout.session_id, event_type, payment_status="unpaid")
    payments.handle_webhook(db_session, body, sig)
    assert payments_of(db_session, user_id)[0].status == PaymentStatus.FAILED
    assert payments.status(db_session, user_id).state == "none"
    with pytest.raises(PaymentRequired):
        payments.require_paid(db_session, user_id)


def test_a_late_failure_never_undoes_a_success(
    db_session: Session,
    fake: FakePaymentGateway,
    recorder: RecordedWebhooks,
    frozen_clock: FrozenClock,
) -> None:
    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    checkout = paid_checkout(db_session, payments, fake, user_id)
    payments.handle_webhook(db_session, *recorder.events[0])
    body, sig = fake.signed_event(checkout.session_id, EXPIRED, payment_status="unpaid")
    payments.handle_webhook(db_session, body, sig)
    assert payments_of(db_session, user_id)[0].status == PaymentStatus.SUCCEEDED


def test_the_payment_is_found_by_metadata_before_its_session_id_is_stored(
    db_session: Session, fake: FakePaymentGateway, frozen_clock: FrozenClock
) -> None:
    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    checkout = payments.start_checkout(db_session, user_id)
    payment = payments_of(db_session, user_id)[0]
    payment.provider_session_id = None  # as if the webhook raced the session-id update
    db_session.commit()
    body, sig = fake.signed_event(checkout.session_id, COMPLETED)
    assert payments.handle_webhook(db_session, body, sig) == "processed"
    assert payments_of(db_session, user_id)[0].status == PaymentStatus.SUCCEEDED


def test_an_event_for_an_unknown_session_is_recorded_and_ignored(
    db_session: Session, frozen_clock: FrozenClock
) -> None:
    other = FakePaymentGateway(webhook_secret=TEST_WEBHOOK_SECRET, base_url="http://testserver")
    payments = service(other, frozen_clock)
    stray = other.create_checkout(
        CheckoutRequest(
            uuid.uuid4(), uuid.uuid4(), 100, "USD", "http://a.test", "http://b.test", "x"
        )
    )
    body, sig = other.signed_event(stray.session_id, COMPLETED)
    assert payments.handle_webhook(db_session, body, sig) == "unknown_session"
    assert payments.handle_webhook(db_session, body, sig) == "duplicate"
    stored = db_session.scalars(select(PaymentEvent)).one()
    assert stored.payment_id is None


def test_the_webhook_never_starts_analysis(
    db_session: Session,
    fake: FakePaymentGateway,
    recorder: RecordedWebhooks,
    frozen_clock: FrozenClock,
) -> None:
    """AC6.3.1: the only effect of a success webhook is the payment row and its event row."""
    user_id = make_user(db_session)
    identity = Identity()
    payments = service(fake, frozen_clock, identity)
    paid_checkout(db_session, payments, fake, user_id)
    calls_before = identity.calls
    payments.handle_webhook(db_session, *recorder.events[0])
    assert identity.calls == calls_before  # no photo snapshot taken, nothing started
    assert recorder.events[1:] == []


# --- Paywall (US6.4) -------------------------------------------------------------------------


class Photos:
    """Stand-in for the photo service's snapshot (C4 ``snapshot_for_run``)."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    def snapshot_for_run(self, _session: Session, _user_id: uuid.UUID) -> dict[str, uuid.UUID]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return {"front": uuid.UUID(int=1)}


def test_no_payment_is_402_and_payment_is_checked_before_the_photos(
    db_session: Session, fake: FakePaymentGateway, frozen_clock: FrozenClock
) -> None:
    """AC6.4.1, AC6.4.2: 402 first, even when the set is also inconsistent."""
    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    photos = Photos(PhotoIdentityMismatch(["left_3q"]))
    with pytest.raises(PaymentRequired) as caught:
        paid_photo_snapshot(payments, photos, db_session, user_id)  # type: ignore[arg-type]
    assert caught.value.status_code == 402
    assert photos.calls == 0
    insert_payment(db_session, user_id, now=frozen_clock.now(), status=PaymentStatus.PENDING)
    with pytest.raises(PaymentRequired):  # pending is not paid
        payments.require_paid(db_session, user_id)


def test_a_paid_user_with_a_failed_photo_set_never_gets_a_snapshot(
    db_session: Session, fake: FakePaymentGateway, frozen_clock: FrozenClock
) -> None:
    """AC6.4.3: a set that failed validation stops the analysis start with 409."""
    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    insert_payment(db_session, user_id, now=frozen_clock.now(), status=PaymentStatus.SUCCEEDED)
    with pytest.raises(PhotoSetIncomplete):
        paid_photo_snapshot(payments, Photos(PhotoSetIncomplete()), db_session, user_id)  # type: ignore[arg-type]
    snapshot = paid_photo_snapshot(payments, Photos(), db_session, user_id)  # type: ignore[arg-type]
    assert snapshot == {"front": uuid.UUID(int=1)}
    assert payments.entitlement(db_session, user_id).paid is True
    assert payments.payment_state(db_session, user_id) == "paid"


def test_webhook_event_dataclass_reads_metadata() -> None:
    event = WebhookEvent("evt", COMPLETED, None, uuid.UUID(int=5), "paid")
    assert event.is_success
    assert event.payment_id == uuid.UUID(int=5)


def test_the_public_ports_delegate_to_the_service(
    db_session: Session, fake: FakePaymentGateway, frozen_clock: FrozenClock
) -> None:
    from app.payments.public import entitlement, payment_state, require_paid

    user_id = make_user(db_session)
    payments = service(fake, frozen_clock)
    assert entitlement(payments, db_session, user_id).paid is False
    assert payment_state(payments, db_session, user_id) == "none"
    with pytest.raises(PaymentRequired):
        require_paid(payments, db_session, user_id)
    insert_payment(db_session, user_id, now=frozen_clock.now(), status=PaymentStatus.SUCCEEDED)
    assert require_paid(payments, db_session, user_id).paid is True
