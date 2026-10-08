"""Image generation through the real API, worker and pipeline (US9.1-US9.5).

The image vendor is the recording FAKE; no paid service is ever called (NFR-013).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.errors import AiRateLimitError, AiRequestRejectedError
from app.analysis.models import AnalysisImageSlot, AnalysisResult, AnalysisStep
from app.images.catalog import AI_LABEL, CATALOG
from app.media.models import MediaFile
from tests.analysis.conftest import current, rerun, start, step_states
from tests.factories import SignedInUser
from tests.identity.conftest import bearer
from tests.images.conftest import ImageHarness


def images(client: TestClient, user: SignedInUser) -> Any:
    return client.get("/images", headers=bearer(user.access_token))


def retry(client: TestClient, user: SignedInUser, slot_id: str) -> Any:
    return client.post(f"/images/{slot_id}/retry", headers=bearer(user.access_token))


def slots(db_session: Session) -> dict[str, AnalysisImageSlot]:
    rows = db_session.scalars(select(AnalysisImageSlot)).all()
    return {row.slot_key: row for row in rows}


def run_to_done(client: TestClient, user: SignedInUser, harness: ImageHarness) -> None:
    assert start(client, user).status_code == 202
    harness.drain()


def fail_run_with_four_failures(
    client: TestClient, user: SignedInUser, harness: ImageHarness, db_session: Session
) -> str:
    """The fake fails 4 times, so the first slot ends "not available yet" (AC9.5.2)."""
    harness.editor.fail_next(times=4)
    run_to_done(client, user, harness)
    marked = [key for key, slot in slots(db_session).items() if slot.status == "not_available_yet"]
    assert len(marked) == 1
    return marked[0]


# --- US9.1-US9.4: the images exist, are private, labelled and complete ------------------------


def test_a_completed_run_has_24_private_images_made_from_my_front_photo(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC9.1.1, AC9.1.2, AC9.4.2."""
    run_to_done(client, paid, image_harness)

    body = current(client, paid).json()
    assert body["status"] == "completed"
    assert step_states(body)["generating_images"] == "done"
    rows = slots(db_session)
    assert len(rows) == 24
    assert {row.status for row in rows.values()} == {"ready"}
    assert all(row.auto_attempts == 1 for row in rows.values())
    files = db_session.scalars(select(MediaFile).where(MediaFile.kind == "ai_image")).all()
    assert len(files) == 24  # one stored image per slot, linked to the run
    assert {file.id for file in files} == {row.media_file_id for row in rows.values()}
    assert {str(file.owner_user_id) for file in files} == {paid.user_id}
    # 11 feature images + 13 AI Visuals images (5 + 5 + 3).
    assert sum(1 for r in rows.values() if r.slot_kind == "feature_after") == 11
    assert sum(1 for r in rows.values() if r.slot_kind != "feature_after") == 13

    calls = image_harness.editor.calls
    assert len(calls) == 24
    photos = db_session.scalars(
        select(MediaFile).where(
            MediaFile.owner_user_id == uuid.UUID(paid.user_id), MediaFile.kind == "photo"
        )
    ).all()
    assert {call.label for call in calls} == {"front"}  # always the user's own front photo
    assert {call.fidelity for call in calls} == {"high"}  # the configured setting
    assert {call.source_bytes for call in calls} <= {photo.size_bytes for photo in photos}
    assert {call.instruction for call in calls} == {spec.instruction for spec in CATALOG}
    result = db_session.scalars(select(AnalysisResult)).one()
    assert result.result["imageSlots"] == 24


def test_the_images_endpoint_groups_the_slots_and_labels_every_image(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    """AC9.2.1, AC9.3.1, AC9.4.1, AC9.4.2."""
    run_to_done(client, paid, image_harness)

    response = images(client, paid)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["generating"] is False
    assert body["frontPhotoUrl"].startswith("/media/")  # the aging stack's first card (own photo)
    by_group: dict[str, list[dict[str, Any]]] = {}
    for slot in body["slots"]:
        by_group.setdefault(slot["group"], []).append(slot)
    assert {g: len(v) for g, v in by_group.items()} == {
        "feature": 11,
        "hairstyle": 5,
        "outfit": 5,
        "aging": 3,
    }
    assert [s["slotId"] for s in by_group["aging"]] == [
        "aging_plus_3",
        "aging_plus_5",
        "aging_plus_10",
    ]
    for slot in body["slots"]:
        assert slot["status"] == "ready"
        assert slot["imageUrl"].startswith("/media/")
        assert slot["aiLabel"] == AI_LABEL
        assert slot["retriesLeft"] == 3
    image = client.get(by_group["hairstyle"][0]["imageUrl"], headers=bearer(paid.access_token))
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"


def test_another_user_cannot_see_or_retry_my_images(
    client: TestClient,
    paid: SignedInUser,
    make_paid_user: Any,
    image_harness: ImageHarness,
) -> None:
    """AC9.1.3: 404, never 403."""
    run_to_done(client, paid, image_harness)
    url = images(client, paid).json()["slots"][0]["imageUrl"]
    other = make_paid_user()

    assert client.get(url, headers=bearer(other.access_token)).status_code == 404
    assert images(client, other).status_code == 404  # no run of their own yet
    assert retry(client, other, "hairstyle_1").status_code == 404
    assert client.get("/images").status_code == 401
    assert client.post("/images/hairstyle_1/retry").status_code == 401


# --- US9.5: retries, "not available yet" and the report still publishing ----------------------


def test_three_failures_then_success_stores_the_image_after_exactly_four_calls(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC9.5.1."""
    image_harness.editor.fail_next(times=3)
    run_to_done(client, paid, image_harness)

    rows = slots(db_session)
    assert {row.status for row in rows.values()} == {"ready"}
    assert sorted(row.auto_attempts for row in rows.values()) == [1] * 23 + [4]
    assert len(image_harness.editor.calls) == 27  # 4 for the first image, 1 for each other


def test_four_failures_leave_the_slot_not_available_yet_and_the_report_is_published(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC9.5.2."""
    key = fail_run_with_four_failures(client, paid, image_harness, db_session)

    assert slots(db_session)[key].auto_attempts == 4
    assert len(image_harness.editor.calls) == 4 + 23
    assert current(client, paid).json()["status"] == "completed"  # the report publishes
    assert db_session.scalars(select(AnalysisResult)).one() is not None
    marked = next(s for s in images(client, paid).json()["slots"] if s["slotId"] == key)
    assert marked["status"] == "not_available"
    assert marked["imageUrl"] is None
    assert marked["retriesLeft"] == 3


def test_rate_limits_back_off_and_count_as_attempts(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC7.6.4: the vendor hint is honoured; each answer counts toward the 4 calls."""
    image_harness.editor.fail_next(AiRateLimitError(retry_after=7), times=2)
    image_harness.editor.fail_next(AiRateLimitError(), times=1)
    run_to_done(client, paid, image_harness)

    assert image_harness.sleeps == [7, 7, 0.0]  # third has no hint: the configured back-off (0)
    assert max(row.auto_attempts for row in slots(db_session).values()) == 4


def test_a_request_the_vendor_refuses_is_not_retried(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    image_harness.editor.fail_next(AiRequestRejectedError("no"), times=1)
    run_to_done(client, paid, image_harness)

    rows = slots(db_session)
    assert [r.auto_attempts for r in rows.values() if r.status == "not_available_yet"] == [1]
    assert len(image_harness.editor.calls) == 24


def test_an_answer_that_is_not_an_image_counts_as_a_failed_attempt(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    image_harness.editor.malformed_next(times=1)
    run_to_done(client, paid, image_harness)

    assert sorted(r.auto_attempts for r in slots(db_session).values()) == [1] * 23 + [2]
    stored = db_session.scalars(select(MediaFile).where(MediaFile.kind == "ai_image")).all()
    assert len(stored) == 24


def test_the_narratives_are_saved_before_the_first_image_is_requested(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC9.5.5: while images generate, the report text is already stored."""
    seen: list[bool] = []
    real_edit = image_harness.editor.edit

    def spy(source: Any, instruction: str, fidelity: str) -> bytes:
        steps = {s.key: s for s in db_session.scalars(select(AnalysisStep)).all()}
        writing = steps["writing"]
        seen.append(
            writing.status == "done"
            and writing.output is not None
            and "reportText" in writing.output
            and steps["generating_images"].status != "done"
        )
        return real_edit(source, instruction, fidelity)

    image_harness.editor.edit = spy  # type: ignore[method-assign]
    run_to_done(client, paid, image_harness)

    assert seen
    assert all(seen)


def test_a_restart_only_generates_the_images_that_are_still_pending(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """No second paid call for an image already stored (AC7.6.2)."""
    real_edit = image_harness.editor.edit
    count = 0

    def crash_on_third(source: Any, instruction: str, fidelity: str) -> bytes:
        nonlocal count
        count += 1
        if count == 3:
            raise RuntimeError("worker died")
        return real_edit(source, instruction, fidelity)

    image_harness.editor.edit = crash_on_third  # type: ignore[method-assign]
    run_to_done(client, paid, image_harness)
    assert current(client, paid).json()["status"] == "failed"
    ready_before = [r.status for r in slots(db_session).values()].count("ready")
    calls_before = count
    assert 2 <= ready_before < 24

    assert rerun(client, paid).status_code == 202
    image_harness.drain()

    assert current(client, paid).json()["status"] == "completed"
    assert {r.status for r in slots(db_session).values()} == {"ready"}
    assert count == calls_before + 24 - ready_before  # stored images were not requested again


# --- Manual retry ------------------------------------------------------------------------------


def test_a_manual_retry_that_succeeds_shows_the_new_image(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC9.5.3 (success)."""
    key = fail_run_with_four_failures(client, paid, image_harness, db_session)
    calls_before = len(image_harness.editor.calls)

    response = retry(client, paid, key)

    assert response.status_code == 200
    body = response.json()
    assert (body["slotId"], body["status"], body["retriesLeft"]) == (key, "ready", 2)
    assert body["imageUrl"].startswith("/media/")
    assert len(image_harness.editor.calls) == calls_before + 1  # one attempt per click
    assert slots(db_session)[key].status == "ready"


def test_a_manual_retry_that_fails_keeps_the_slot_marked_and_uses_up_a_retry(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC9.5.3 (failure)."""
    key = fail_run_with_four_failures(client, paid, image_harness, db_session)
    image_harness.editor.fail_next(times=1)

    body = retry(client, paid, key).json()

    assert (body["status"], body["imageUrl"], body["retriesLeft"]) == ("not_available", None, 2)
    assert slots(db_session)[key].manual_retries == 1


def test_after_three_manual_retries_the_fourth_is_refused_without_a_vendor_call(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness, db_session: Session
) -> None:
    """AC9.5.4."""
    key = fail_run_with_four_failures(client, paid, image_harness, db_session)
    for left in (2, 1, 0):
        image_harness.editor.fail_next(times=1)
        assert retry(client, paid, key).json()["retriesLeft"] == left
    calls_before = len(image_harness.editor.calls)

    refused = retry(client, paid, key)

    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "IMAGE_RETRY_NOT_AVAILABLE"
    assert len(image_harness.editor.calls) == calls_before


def test_a_ready_or_unknown_image_cannot_be_retried(
    client: TestClient, paid: SignedInUser, image_harness: ImageHarness
) -> None:
    run_to_done(client, paid, image_harness)
    calls_before = len(image_harness.editor.calls)

    ready = retry(client, paid, "hairstyle_1")
    unknown = retry(client, paid, "hairstyle_99")

    assert ready.status_code == 409
    assert unknown.status_code == 404
    assert len(image_harness.editor.calls) == calls_before
