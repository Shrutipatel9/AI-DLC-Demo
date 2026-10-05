"""The shared same-person check over stored photos (AC5.6.5; contract C4; [IV] §1, §5).

Real PostgreSQL, the real MediaPipe model and real stored files. The C4 port functions are
the ones checkout (U5) and "Start Analysis" (U6) will call.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.face.public import FaceGeometry, FaceResult, MediaPipeFaceGeometry, RgbImage
from app.photos.identity import evaluate_signatures, signature
from app.photos.public import (
    PhotoIntakeService,
    check_identity,
    get_photo_set_state,
    snapshot_for_run,
)
from app.platform.errors import PhotoIdentityMismatch, PhotoSetIncomplete
from tests.faces import (
    A_FRONT,
    A_LEFT,
    A_RIGHT,
    B_LEFT,
    MODEL_PATH,
    fixture_pixels,
    portrait_pixels,
)
from tests.factories import SignedInUser
from tests.photos.conftest import upload


class CountingGeometry:
    """Wraps the real FaceGeometry and counts detections (proves nothing is cached)."""

    def __init__(self, inner: FaceGeometry) -> None:
        self.inner = inner
        self.calls = 0

    def load(self) -> None:
        self.inner.load()

    def detect(self, image: RgbImage) -> FaceResult:
        self.calls += 1
        return self.inner.detect(image)


def service_of(app: FastAPI) -> PhotoIntakeService:
    service: PhotoIntakeService = app.state.photos
    return service


def upload_set(client: TestClient, user: SignedInUser, left: str = A_LEFT) -> Any:
    for angle, name in (("front", A_FRONT), ("left_3q", left), ("right_3q", A_RIGHT)):
        response = upload(client, user, angle, name)
        assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def session(session_factory: Callable[[], Session]) -> Session:
    return session_factory()


def test_consistent_set_through_the_c4_port(
    app: FastAPI, client: TestClient, submitted: SignedInUser, session: Session
) -> None:
    upload_set(client, submitted)
    user_id = uuid.UUID(submitted.user_id)
    result = check_identity(service_of(app), session, user_id)
    assert result.status == "consistent"
    assert result.mismatched_angles == ()
    state = get_photo_set_state(service_of(app), session, user_id)
    assert state.complete
    assert state.consistent
    snapshot = snapshot_for_run(service_of(app), session, user_id)
    assert set(snapshot) == {"front", "left_3q", "right_3q"}
    assert all(isinstance(file_id, uuid.UUID) for file_id in snapshot.values())


def test_every_call_recomputes_from_the_stored_photos(
    app: FastAPI, client: TestClient, submitted: SignedInUser, session: Session
) -> None:
    upload_set(client, submitted)
    service = service_of(app)
    counting = CountingGeometry(service.geometry)
    service.geometry = counting
    user_id = uuid.UUID(submitted.user_id)

    assert check_identity(service, session, user_id).status == "consistent"
    assert check_identity(service, session, user_id).status == "consistent"
    assert counting.calls == 6  # three photos measured again on each call: nothing cached


def test_a_retake_changes_the_next_result_with_no_memory_of_the_last(
    app: FastAPI, client: TestClient, submitted: SignedInUser, session: Session
) -> None:
    upload_set(client, submitted, left=B_LEFT)
    service, user_id = service_of(app), uuid.UUID(submitted.user_id)
    mismatch = check_identity(service, session, user_id)
    assert mismatch.status == "mismatch"
    assert mismatch.mismatched_angles == ("left_3q",)
    with pytest.raises(PhotoIdentityMismatch) as raised:
        snapshot_for_run(service, session, user_id)
    assert raised.value.mismatched_angles == ["left_3q"]
    assert get_photo_set_state(service, session, user_id).consistent is False

    assert upload(client, submitted, "left_3q", A_LEFT).status_code == 200
    session.expire_all()
    assert check_identity(service, session, user_id).status == "consistent"


def test_an_incomplete_set_is_not_checked_and_cannot_be_snapshotted(
    app: FastAPI, client: TestClient, submitted: SignedInUser, session: Session
) -> None:
    assert upload(client, submitted, "front", A_FRONT).status_code == 200
    assert upload(client, submitted, "left_3q", B_LEFT).status_code == 200
    service, user_id = service_of(app), uuid.UUID(submitted.user_id)
    result = check_identity(service, session, user_id)
    assert result.status == "incomplete"  # two angles: not run, not blocking (AC5.6.4)
    assert result.mismatched_angles == ()
    with pytest.raises(PhotoSetIncomplete):
        snapshot_for_run(service, session, user_id)
    state = get_photo_set_state(service, session, user_id)
    assert not state.complete
    assert not state.consistent


def test_a_stored_file_that_disappeared_is_flagged_for_retake(
    app: FastAPI,
    client: TestClient,
    submitted: SignedInUser,
    session: Session,
    media_root: Path,
) -> None:
    body = upload_set(client, submitted)
    front_url = next(p["imageUrl"] for p in body["photos"] if p["angle"] == "front")
    front_file = media_root / submitted.user_id / f"{front_url.removeprefix('/media/')}.png"
    front_file.unlink()
    result = check_identity(service_of(app), session, uuid.UUID(submitted.user_id))
    assert result.status == "mismatch"
    assert result.mismatched_angles == ("front",)


def test_real_faces_through_the_model_separate_people() -> None:
    # One real face (MediaPipe's sample portrait) against the synthetic person, with no
    # overrides: the real model's signatures give a mismatch for the odd one out.
    geometry = MediaPipeFaceGeometry(MODEL_PATH)
    faces = {
        "front": geometry.detect(fixture_pixels(A_FRONT)),
        "left_3q": geometry.detect(fixture_pixels(A_LEFT)),
        "right_3q": geometry.detect(portrait_pixels()),
    }
    signatures = {angle: signature(face) for angle, face in faces.items()}  # type: ignore[arg-type]
    result = evaluate_signatures(("front", "left_3q", "right_3q"), signatures, 0.6)
    assert result.status == "mismatch"
    assert result.mismatched_angles == ("right_3q",)
