"""``/photos`` API with real PostgreSQL, real files and the real MediaPipe model (contract C1;
US5.1, US5.2, US5.5, US5.6, US5.10, US5.11).
"""

from __future__ import annotations

import io
from typing import Any

import pillow_heif
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.media.models import MediaFile
from app.photos.models import Photo
from app.platform.email.fake import RecordingEmailSender
from tests.faces import A_FRONT, A_LEFT, A_RIGHT, B_LEFT, NO_FACE, fixture_pixels
from tests.factories import SignedInUser, verified_user
from tests.photos.conftest import ANGLES, bearer, photo_status, upload


def get_set(client: TestClient, user: SignedInUser) -> Any:
    response = client.get("/photos", headers=bearer(user.access_token))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def upload_all(client: TestClient, user: SignedInUser, left: str = A_LEFT) -> Any:
    body: Any = None
    for angle, name in (("front", A_FRONT), ("left_3q", left), ("right_3q", A_RIGHT)):
        response = upload(client, user, angle, name)
        assert response.status_code == 200, response.text
        body = response.json()
    return body


# --- Requirements (US5.1) -----------------------------------------------------------------------


def test_requirements_list_the_rules_guidance_and_configured_angles(
    client: TestClient, submitted: SignedInUser
) -> None:
    response = client.get("/photos/requirements", headers=bearer(submitted.access_token))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert len(body["rules"]) == 7
    assert body["rules"][0] == {"id": "no_glasses_hat", "text": "No glasses or hat"}
    assert len(body["guidance"]) == 9
    assert [angle["id"] for angle in body["angles"]] == ANGLES
    assert body["angles"][1]["illustration"] == "left"
    assert "turnHint" in body["angles"][1]
    assert body["maxUploadBytes"] == 10 * 1024 * 1024
    assert body["acceptedTypes"] == ["image/jpeg", "image/png", "image/heic"]
    assert "yawRange" not in body["angles"][0]


def test_photos_need_a_submitted_questionnaire(
    client: TestClient, email_fake: RecordingEmailSender
) -> None:
    user = verified_user(client, email_fake)
    for response in (
        client.get("/photos/requirements", headers=bearer(user.access_token)),
        client.get("/photos", headers=bearer(user.access_token)),
        upload(client, user, "front", A_FRONT),
    ):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "QUESTIONNAIRE_NOT_SUBMITTED"


def test_photos_need_a_signed_in_user(client: TestClient) -> None:
    assert client.get("/photos").status_code == 401
    assert client.get("/photos/requirements").status_code == 401
    response = client.put("/photos/front", files={"file": ("a.png", b"x", "image/png")})
    assert response.status_code == 401


# --- The photo set and upload (US5.2) ----------------------------------------------------------


def test_a_new_set_has_every_angle_missing(client: TestClient, submitted: SignedInUser) -> None:
    body = get_set(client, submitted)
    assert body["requiredAngles"] == ANGLES
    assert body["acceptedCount"] == 0
    assert [photo["status"] for photo in body["photos"]] == ["missing"] * 3
    assert body["identity"] == {"status": "incomplete", "mismatchedAngles": []}


def test_an_accepted_photo_is_stored_and_counted(
    client: TestClient, submitted: SignedInUser
) -> None:
    response = upload(client, submitted, "front", A_FRONT, capture_method="camera")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    front = photo_status(body, "front")
    assert front["status"] == "accepted"
    assert front["imageUrl"].startswith("/media/")
    assert front["captureMethod"] == "camera"
    assert front["reasons"] == []
    assert body["acceptedCount"] == 1  # "1 of 3" (AC5.2.6)
    assert body["identity"]["status"] == "incomplete"  # two angles missing: not blocking


def test_a_complete_same_person_set_is_consistent(
    client: TestClient, submitted: SignedInUser
) -> None:
    body = upload_all(client, submitted)
    assert body["acceptedCount"] == 3
    assert body["identity"] == {"status": "consistent", "mismatchedAngles": []}
    assert get_set(client, submitted)["identity"]["status"] == "consistent"


def test_a_different_person_is_flagged_and_a_retake_clears_it(
    client: TestClient, submitted: SignedInUser
) -> None:
    body = upload_all(client, submitted, left=B_LEFT)
    assert body["identity"] == {"status": "mismatch", "mismatchedAngles": ["left_3q"]}
    assert photo_status(body, "left_3q")["status"] == "accepted"  # passed its own checks
    assert get_set(client, submitted)["identity"]["mismatchedAngles"] == ["left_3q"]

    retaken = upload(client, submitted, "left_3q", A_LEFT).json()
    assert retaken["identity"] == {"status": "consistent", "mismatchedAngles": []}


def test_a_retake_replaces_the_photo_so_only_one_exists(
    client: TestClient, submitted: SignedInUser, db_session: Session
) -> None:
    first = photo_status(upload(client, submitted, "front", A_FRONT).json(), "front")
    second = photo_status(upload(client, submitted, "front", A_FRONT).json(), "front")
    assert first["imageUrl"] != second["imageUrl"]
    rows = db_session.scalar(
        select(func.count()).select_from(Photo).where(Photo.user_id == submitted.user_id)
    )
    files = db_session.scalar(
        select(func.count())
        .select_from(MediaFile)
        .where(MediaFile.owner_user_id == submitted.user_id)
    )
    assert (rows, files) == (1, 1)  # AC5.2.4, AC1.10.3


def test_users_only_see_their_own_photos(
    client: TestClient,
    submitted: SignedInUser,
    email_fake: RecordingEmailSender,
    seed_definition: Any,
) -> None:
    from tests.photos.conftest import submitted_user_for

    upload_all(client, submitted)
    other = submitted_user_for(client, email_fake, seed_definition)
    body = get_set(client, other)
    assert body["acceptedCount"] == 0
    assert all(photo["imageUrl"] is None for photo in body["photos"])


# --- Rejections (US5.5, US5.10) ----------------------------------------------------------------


def test_a_photo_without_a_face_is_rejected_with_its_reason(
    client: TestClient, submitted: SignedInUser
) -> None:
    response = upload(client, submitted, "front", NO_FACE)
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "PHOTO_REJECTED"
    assert error["details"] == [{"angle": "front", "reason": "NO_FACE"}]
    front = photo_status(get_set(client, submitted), "front")
    assert front == {
        "angle": "front",
        "status": "rejected",
        "reasons": ["NO_FACE"],
        "imageUrl": None,
        "captureMethod": None,
        "updatedAt": front["updatedAt"],
    }
    accepted = photo_status(upload(client, submitted, "front", A_FRONT).json(), "front")
    assert accepted["status"] == "accepted"
    assert accepted["reasons"] == []


def test_the_wrong_angle_is_rejected_for_pose(client: TestClient, submitted: SignedInUser) -> None:
    response = upload(client, submitted, "left_3q", A_FRONT)
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [{"angle": "left_3q", "reason": "POSE_MISMATCH"}]


def test_a_bad_retake_keeps_the_accepted_photo(client: TestClient, submitted: SignedInUser) -> None:
    good = photo_status(upload(client, submitted, "front", A_FRONT).json(), "front")
    assert upload(client, submitted, "front", NO_FACE).status_code == 422
    after = photo_status(get_set(client, submitted), "front")
    assert after["status"] == "accepted"
    assert after["imageUrl"] == good["imageUrl"]


def test_unsupported_types_are_refused_with_415(
    client: TestClient, submitted: SignedInUser
) -> None:
    gif = io.BytesIO()
    Image.fromarray(fixture_pixels(A_FRONT)).save(gif, format="GIF")
    for data, name in ((gif.getvalue(), "face.gif"), (b"%PDF-1.7 not a photo", "face.pdf")):
        # The browser's claimed type is ignored: the bytes decide.
        response = upload(client, submitted, "front", data=data, filename=name)
        assert response.status_code == 415
        assert response.json()["error"]["code"] == "PHOTO_UNSUPPORTED_TYPE"
    assert photo_status(get_set(client, submitted), "front")["status"] == "missing"


def test_a_heic_photo_is_accepted_and_stored_as_jpeg(
    client: TestClient, submitted: SignedInUser
) -> None:
    heic = io.BytesIO()
    pillow_heif.from_pillow(Image.fromarray(fixture_pixels(A_FRONT))).save(heic, format="HEIF")
    response = upload(
        client,
        submitted,
        "front",
        data=heic.getvalue(),
        filename="IMG.HEIC",
        content_type="image/heic",
    )
    assert response.status_code == 200, response.text
    image_url = photo_status(response.json(), "front")["imageUrl"]
    stored = client.get(image_url, headers=bearer(submitted.access_token))
    assert stored.headers["content-type"] == "image/jpeg"
    assert stored.content.startswith(b"\xff\xd8\xff")


def test_a_broken_image_is_rejected_as_unreadable(
    client: TestClient, submitted: SignedInUser
) -> None:
    response = upload(client, submitted, "front", data=b"\xff\xd8\xff\xe0broken", filename="a.jpg")
    assert response.status_code == 422
    assert response.json()["error"]["details"] == [{"angle": "front", "reason": "UNREADABLE"}]


def test_a_photo_over_the_limit_is_refused_with_413(
    client: TestClient, submitted: SignedInUser
) -> None:
    big = b"\xff\xd8\xff" + b"0" * (10 * 1024 * 1024)
    response = upload(client, submitted, "front", data=big, filename="big.jpg")
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PHOTO_TOO_LARGE"
    assert "10 MB" in response.json()["error"]["message"]


def test_an_oversized_body_is_refused_before_it_is_parsed(
    client: TestClient, submitted: SignedInUser
) -> None:
    response = client.put(
        "/photos/front",
        content=b"x" * (10 * 1024 * 1024 + 200 * 1024),
        headers={**bearer(submitted.access_token), "Content-Type": "multipart/form-data; b=x"},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PHOTO_TOO_LARGE"


def test_unknown_and_malformed_angles(client: TestClient, submitted: SignedInUser) -> None:
    unknown = upload(client, submitted, "profile", A_FRONT)
    assert unknown.status_code == 404
    assert unknown.json()["error"]["code"] == "NOT_FOUND"
    assert upload(client, submitted, "Front!", A_FRONT).status_code == 422


def test_the_file_field_and_capture_method_are_validated(
    client: TestClient, submitted: SignedInUser
) -> None:
    missing = client.put("/photos/front", data={}, headers=bearer(submitted.access_token))
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "VALIDATION_FAILED"
    wrong = upload(client, submitted, "front", A_FRONT, capture_method="scanner")
    assert wrong.status_code == 422
