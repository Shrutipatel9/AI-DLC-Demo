"""FaceGeometry with the real pinned MediaPipe model (US1.11; AC1.11.1-AC1.11.3).

Images: the committed synthetic renders (tests/fixtures/faces) and MediaPipe's own sample
portrait (one real face, downloaded with the model).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.face import mediapipe_landmarker
from app.face.mediapipe_landmarker import yaw_from_matrix
from app.face.model import LANDMARK_COUNT, MODEL_SHA256, FaceModelError, file_sha256, verify_model
from app.face.overrides import OverrideFaceGeometry, OverridesFileError, load_overrides
from app.face.public import (
    FaceFound,
    FaceGeometry,
    MediaPipeFaceGeometry,
    MultipleFaces,
    NoFace,
    build_face_geometry,
    pixel_hash,
)
from app.main import create_app
from tests.faces import (
    A_FRONT,
    A_LEFT,
    A_RIGHT,
    B_LEFT,
    MODEL_PATH,
    NO_FACE,
    OVERRIDES_PATH,
    fixture_pixels,
    portrait_pixels,
)
from tests.helpers import make_settings


def test_one_face_gives_478_landmarks(face_geometry: FaceGeometry) -> None:
    for image in (fixture_pixels(A_FRONT), portrait_pixels()):
        result = face_geometry.detect(image)
        assert isinstance(result, FaceFound)
        assert len(result.landmarks) == LANDMARK_COUNT
        assert (result.height, result.width) == image.shape[:2]
        assert result.points_px().shape == (LANDMARK_COUNT, 2)
        assert all(0.0 <= x <= 1.0 and 0.0 <= y <= 1.0 for x, y, _ in result.landmarks)


def test_no_face_is_a_typed_result(face_geometry: FaceGeometry) -> None:
    assert isinstance(face_geometry.detect(fixture_pixels(NO_FACE)), NoFace)


def test_two_faces_are_a_typed_result(face_geometry: FaceGeometry) -> None:
    front = fixture_pixels(A_FRONT)
    result = face_geometry.detect(np.concatenate([front, front], axis=1))
    assert isinstance(result, MultipleFaces)
    assert result.count == 2


def test_the_same_image_twice_gives_identical_landmarks(face_geometry: FaceGeometry) -> None:
    first = face_geometry.detect(portrait_pixels())
    second = face_geometry.detect(portrait_pixels())
    assert isinstance(first, FaceFound)
    assert first == second


def test_results_are_not_cached(face_geometry: FaceGeometry) -> None:
    image = fixture_pixels(A_FRONT).copy()
    before = face_geometry.detect(image)
    image[:] = 246  # the same array object, now without a face
    assert isinstance(before, FaceFound)
    assert isinstance(face_geometry.detect(image), NoFace)


def test_yaw_tells_front_from_each_three_quarter_turn(face_geometry: FaceGeometry) -> None:
    yaws = {}
    for name in (A_FRONT, A_LEFT, A_RIGHT):
        result = face_geometry.detect(fixture_pixels(name))
        assert isinstance(result, FaceFound)
        yaws[name] = result.yaw_degrees
    assert abs(yaws[A_FRONT]) < 12
    assert yaws[A_LEFT] < -15  # left cheek to the camera: nose to the image's left
    assert yaws[A_RIGHT] > 15


def test_the_model_is_loaded_once_per_process(face_geometry: FaceGeometry) -> None:
    face_geometry.detect(fixture_pixels(A_FRONT))
    loaded = dict(mediapipe_landmarker._LANDMARKERS)
    second = MediaPipeFaceGeometry(MODEL_PATH)
    second.load()
    second.detect(fixture_pixels(A_FRONT))
    assert loaded == mediapipe_landmarker._LANDMARKERS  # the same object, no second load


def test_detect_refuses_anything_but_rgb_uint8(face_geometry: FaceGeometry) -> None:
    with pytest.raises(ValueError, match="RGB"):
        face_geometry.detect(np.zeros((10, 10), dtype=np.uint8))
    with pytest.raises(ValueError, match="RGB"):
        face_geometry.detect(np.zeros((10, 10, 3), dtype=np.float32))  # type: ignore[arg-type]


def test_yaw_from_a_rotation_matrix() -> None:
    angle = np.radians(30)
    turned = [
        [np.cos(angle), 0, np.sin(angle), 0],
        [0, 1, 0, 0],
        [-np.sin(angle), 0, np.cos(angle), 0],
        [0, 0, 0, 1],
    ]
    assert yaw_from_matrix(turned) == pytest.approx(30.0)
    assert yaw_from_matrix(np.eye(4)) == pytest.approx(0.0)


# --- The pinned model -------------------------------------------------------------------------


def test_the_fetched_model_is_the_pinned_version() -> None:
    assert file_sha256(MODEL_PATH) == MODEL_SHA256
    verify_model(MODEL_PATH)


def test_a_missing_model_names_the_fix(tmp_path: Path) -> None:
    with pytest.raises(FaceModelError, match=r"tools\.fetch_face_model"):
        verify_model(tmp_path / "absent.task")
    with pytest.raises(FaceModelError):
        MediaPipeFaceGeometry(tmp_path / "absent.task").load()


def test_a_different_model_file_is_refused(tmp_path: Path) -> None:
    other = tmp_path / "other.task"
    shutil.copyfile(MODEL_PATH, other)
    with other.open("ab") as handle:
        handle.write(b"tampered")
    with pytest.raises(FaceModelError, match="SHA-256 mismatch"):
        MediaPipeFaceGeometry(other).load()


def test_start_up_fails_when_the_model_is_missing(tmp_path: Path) -> None:
    settings = make_settings(
        FACE_MODEL_PATH=str(tmp_path / "absent.task"), CHECK_MIGRATIONS_AT_STARTUP="false"
    )
    app = create_app(settings)
    with pytest.raises(FaceModelError), TestClient(app):
        pass


def test_start_up_skips_the_model_when_preload_is_off(tmp_path: Path) -> None:
    settings = make_settings(
        FACE_MODEL_PATH=str(tmp_path / "absent.task"),
        FACE_MODEL_PRELOAD="false",
        CHECK_MIGRATIONS_AT_STARTUP="false",
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200


# --- Landmark overrides (development/test only) ------------------------------------------------


def test_overrides_replace_the_model_only_for_known_images(face_geometry: FaceGeometry) -> None:
    wrapped = OverrideFaceGeometry(face_geometry, OVERRIDES_PATH)
    wrapped.load()
    overridden = wrapped.detect(fixture_pixels(B_LEFT))
    assert isinstance(overridden, FaceFound)
    entry = json.loads(OVERRIDES_PATH.read_text())["images"][pixel_hash(fixture_pixels(B_LEFT))]
    assert overridden.landmarks[61] == tuple(entry["landmarks"][61])
    assert wrapped.detect(fixture_pixels(A_FRONT)) == face_geometry.detect(fixture_pixels(A_FRONT))
    assert isinstance(wrapped.detect(fixture_pixels(NO_FACE)), NoFace)


def test_build_face_geometry_selects_the_overrides_only_when_configured() -> None:
    plain = build_face_geometry(make_settings(FACE_MODEL_PATH=str(MODEL_PATH)))
    assert isinstance(plain, MediaPipeFaceGeometry)
    wrapped = build_face_geometry(
        make_settings(
            FACE_MODEL_PATH=str(MODEL_PATH), FACE_LANDMARK_OVERRIDES_FILE=str(OVERRIDES_PATH)
        )
    )
    assert isinstance(wrapped, OverrideFaceGeometry)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"version": 2, "images": {}}),
        json.dumps({"version": 1, "images": {"abc": {"landmarks": [[0, 0, 0]]}}}),
        json.dumps([1, 2]),
    ],
)
def test_malformed_overrides_are_refused(tmp_path: Path, content: str) -> None:
    path = tmp_path / "overrides.json"
    path.write_text(content)
    with pytest.raises(OverridesFileError):
        load_overrides(path)


def test_missing_overrides_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(OverridesFileError, match="cannot read"):
        load_overrides(tmp_path / "absent.json")
