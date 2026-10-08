"""The next-step rule through the real API, on real PostgreSQL (US11.8, US5.7).

One test per row of the AC11.8.1 table, plus the re-route of an inconsistent set and the
"recomputed every call" rule. Paid services are fakes; no network is used.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.payments.models import PaymentStatus
from app.platform.clock import FrozenClock
from tests.analysis.conftest import start
from tests.faces import B_LEFT
from tests.factories import SignedInUser
from tests.identity.conftest import bearer
from tests.journey.conftest import (
    ImageHarness,
    give_consent,
    insert_payment,
    run_to_done,
    upload,
)


def next_step(client: TestClient, user: SignedInUser) -> dict[str, Any]:
    """``GET /journey/next-step``; asserts 200 and no-store."""
    response = client.get("/journey/next-step", headers=bearer(user.access_token))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body: dict[str, Any] = response.json()
    return body


def test_a_user_without_consent_is_sent_to_consent(client: TestClient, user: SignedInUser) -> None:
    """AC11.8.1 row 1."""
    assert next_step(client, user) == {"step": "consent", "flaggedAngles": []}


def test_consent_without_a_submitted_questionnaire_is_sent_to_the_questionnaire(
    client: TestClient, user: SignedInUser
) -> None:
    """AC11.8.1 row 2; the answer changes on the very next call (no cache)."""
    assert next_step(client, user)["step"] == "consent"
    give_consent(client, user)
    assert next_step(client, user)["step"] == "questionnaire"


def test_a_submitted_questionnaire_without_photos_is_sent_to_photos(
    client: TestClient, submitted: SignedInUser
) -> None:
    """AC11.8.1 row 3, incomplete set."""
    assert next_step(client, submitted) == {"step": "photos", "flaggedAngles": []}


def test_an_inconsistent_set_is_sent_back_to_photos_with_the_flagged_angles(
    client: TestClient, consistent: SignedInUser
) -> None:
    """AC5.7.1, AC11.8.1 row 3, inconsistent set: the flagged photos travel with the step."""
    assert next_step(client, consistent)["step"] == "payment"
    assert upload(client, consistent, "left_3q", B_LEFT).status_code == 200

    body = next_step(client, consistent)

    assert body["step"] == "photos"
    assert body["flaggedAngles"]
    assert set(body["flaggedAngles"]) <= {"front", "left_3q", "right_3q"}


def test_a_consistent_set_without_payment_is_sent_to_payment(
    client: TestClient, consistent: SignedInUser
) -> None:
    """AC11.8.1 row 4; AC5.7.2: the consistent set skips the photo review screen."""
    assert next_step(client, consistent) == {"step": "payment", "flaggedAngles": []}


def test_a_returned_but_unconfirmed_payment_is_sent_to_confirming(
    client: TestClient, consistent: SignedInUser, db_session: Session, frozen_clock: FrozenClock
) -> None:
    """AC11.8.1 row 5."""
    insert_payment(
        db_session, consistent.user_id, now=frozen_clock.now(), status=PaymentStatus.PENDING
    )
    assert next_step(client, consistent)["step"] == "confirming_payment"


def test_a_failed_payment_attempt_goes_back_to_payment(
    client: TestClient, consistent: SignedInUser, db_session: Session, frozen_clock: FrozenClock
) -> None:
    """A failed attempt is not a successful payment (AC11.8.1 row 4)."""
    insert_payment(
        db_session, consistent.user_id, now=frozen_clock.now(), status=PaymentStatus.FAILED
    )
    assert next_step(client, consistent)["step"] == "payment"


def test_paid_but_not_started_is_sent_to_start_analysis(
    client: TestClient, paid: SignedInUser
) -> None:
    """AC11.8.1 row 6."""
    assert next_step(client, paid)["step"] == "start_analysis"


def test_a_running_analysis_is_sent_to_progress(client: TestClient, paid: SignedInUser) -> None:
    """AC11.8.1 row 7."""
    assert start(client, paid).status_code == 202
    assert next_step(client, paid)["step"] == "progress"


def test_a_finished_report_is_sent_home(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC11.8.1 row 8."""
    run_to_done(client, paid, image_harness)
    assert next_step(client, paid)["step"] == "home"


def test_the_next_step_belongs_to_the_caller_and_needs_a_token(
    client: TestClient, paid: SignedInUser, user: SignedInUser
) -> None:
    """Owner-only: another user's progress never leaks into the answer."""
    assert next_step(client, paid)["step"] == "start_analysis"
    assert next_step(client, user)["step"] == "consent"
    assert client.get("/journey/next-step").status_code == 401
