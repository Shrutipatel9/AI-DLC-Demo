"""Per-photo checks with the real MediaPipe model (US5.5, US5.10; AC5.5.1-AC5.5.3,
AC5.10.1, AC5.10.2).

Each "one check broken" image is derived from a passing photo so that it breaks exactly that
check (AC5.5.2). Thresholds are the configured defaults unless a test changes them.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.face.public import FaceFound, FaceGeometry, RgbImage
from app.photos.catalog import DEFAULT_CATALOG_FILE, PhotoCatalog, load_catalog
from app.photos.checks import CheckThresholds, PhotoReason, check_photo, luminance
from tests.face.conftest import face_geometry  # noqa: F401  (pytest fixture re-used here)
from tests.faces import A_FRONT, A_LEFT, A_RIGHT, NO_FACE, fixture_pixels, portrait_pixels
from tests.helpers import make_settings

BACKGROUND = (246, 246, 243)


@pytest.fixture(scope="module")
def catalog() -> PhotoCatalog:
    return load_catalog(DEFAULT_CATALOG_FILE, ["front", "left_3q", "right_3q"])


@pytest.fixture(scope="module")
def limits() -> CheckThresholds:
    return CheckThresholds.from_settings(make_settings())


def run(
    geometry: FaceGeometry,
    catalog: PhotoCatalog,
    limits: CheckThresholds,
    pixels: RgbImage,
    angle: str = "front",
) -> list[PhotoReason]:
    spec = catalog.angle(angle)
    assert spec is not None
    return check_photo(pixels, geometry.detect(pixels), spec, limits)


def landmarks_of(geometry: FaceGeometry, pixels: RgbImage) -> np.ndarray:
    face = geometry.detect(pixels)
    assert isinstance(face, FaceFound)
    return face.points_px()


def as_array(image: Image.Image) -> RgbImage:
    return np.asarray(image.convert("RGB"), dtype=np.uint8)


# --- Passing photos ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "angle"), [(A_FRONT, "front"), (A_LEFT, "left_3q"), (A_RIGHT, "right_3q")]
)
def test_good_photos_pass_for_their_angle(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
    name: str,
    angle: str,
) -> None:
    assert run(face_geometry, catalog, limits, fixture_pixels(name), angle) == []


def test_a_real_portrait_passes_as_front(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
) -> None:
    assert run(face_geometry, catalog, limits, portrait_pixels()) == []


# --- Exactly one face (AC5.5.1) -------------------------------------------------------------


def test_two_faces_are_rejected_for_exactly_one_face(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
) -> None:
    front = fixture_pixels(A_FRONT)
    pair = np.concatenate([front, front], axis=1)
    assert run(face_geometry, catalog, limits, pair) == [PhotoReason.MULTIPLE_FACES]


def test_no_face_is_rejected(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
) -> None:
    assert run(face_geometry, catalog, limits, fixture_pixels(NO_FACE)) == [PhotoReason.NO_FACE]


def test_a_dark_photo_without_a_face_also_says_too_dark(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
) -> None:
    dark = np.zeros((800, 640, 3), dtype=np.uint8) + 8
    assert run(face_geometry, catalog, limits, dark) == [PhotoReason.TOO_DARK, PhotoReason.NO_FACE]


# --- One check broken at a time (AC5.5.2) ---------------------------------------------------


def test_low_resolution_breaks_only_the_resolution_check(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
) -> None:
    small = as_array(Image.fromarray(fixture_pixels(A_FRONT)).resize((320, 400)))
    assert run(face_geometry, catalog, limits, small) == [PhotoReason.TOO_SMALL]


def test_a_dark_photo_breaks_only_the_brightness_check(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
) -> None:
    dark = (fixture_pixels(A_FRONT).astype(np.float32) * 0.18).astype(np.uint8)
    assert run(face_geometry, catalog, limits, dark) == [PhotoReason.TOO_DARK]


def test_an_overexposed_photo_breaks_only_the_brightness_check(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
) -> None:
    pixels = fixture_pixels(A_FRONT)
    brighter = replace(limits, max_brightness=140.0)  # the face region measures about 150
    assert run(face_geometry, catalog, brighter, pixels) == [PhotoReason.TOO_BRIGHT]


def test_a_face_far_from_the_camera_breaks_only_the_proportion_check(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
) -> None:
    canvas = Image.new("RGB", (1600, 2000), BACKGROUND)
    canvas.paste(Image.fromarray(fixture_pixels(A_FRONT)), (480, 600))
    assert run(face_geometry, catalog, limits, as_array(canvas)) == [PhotoReason.FACE_TOO_SMALL]


def test_a_face_filling_the_frame_breaks_only_the_proportion_check(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
) -> None:
    closer = replace(limits, max_face_fraction=0.1)  # the fixture's face box is about 0.17
    assert run(face_geometry, catalog, closer, fixture_pixels(A_FRONT)) == [
        PhotoReason.FACE_TOO_LARGE
    ]


# --- Pose (AC5.10.1) ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "angle"),
    [(A_FRONT, "left_3q"), (A_FRONT, "right_3q"), (A_LEFT, "front"), (A_RIGHT, "left_3q")],
)
def test_the_wrong_angle_is_a_pose_mismatch(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
    name: str,
    angle: str,
) -> None:
    assert run(face_geometry, catalog, limits, fixture_pixels(name), angle) == [
        PhotoReason.POSE_MISMATCH
    ]


def test_each_angle_explains_which_way_to_turn(catalog: PhotoCatalog) -> None:
    left, right = catalog.angle("left_3q"), catalog.angle("right_3q")
    assert left is not None
    assert right is not None
    assert "to your right" in left.turn_hint
    assert "left cheek" in left.turn_hint
    assert "to your left" in right.turn_hint
    assert "right cheek" in right.turn_hint


# --- Covered eyes or mouth (AC5.10.2) -----------------------------------------------------------


def cover(
    pixels: RgbImage,
    points: np.ndarray,
    indices: list[int],
    colour: tuple[int, ...],
    pad_x: float,
    pad_y: float,
) -> RgbImage:
    image = Image.fromarray(pixels)
    x0, y0 = points[indices].min(axis=0)
    x1, y1 = points[indices].max(axis=0)
    ImageDraw.Draw(image).rectangle((x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y), fill=colour)
    return as_array(image)


EYE_CORNERS = [33, 133, 362, 263, 159, 145, 386, 374]
MOUTH_POINTS = [61, 291, 0, 17]


@pytest.mark.parametrize("source", ["synthetic", "portrait"])
def test_dark_glasses_are_rejected_for_covered_eyes(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
    source: str,
) -> None:
    pixels = fixture_pixels(A_FRONT) if source == "synthetic" else portrait_pixels()
    points = landmarks_of(face_geometry, pixels)
    span = float(np.linalg.norm(points[33] - points[263]))
    covered = cover(pixels, points, EYE_CORNERS, (15, 15, 15), 0.15 * span, 0.12 * span)
    assert run(face_geometry, catalog, limits, covered) == [PhotoReason.EYES_COVERED]


@pytest.mark.parametrize("source", ["synthetic", "portrait"])
def test_a_hand_over_the_mouth_is_rejected_for_a_covered_mouth(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
    limits: CheckThresholds,
    source: str,
) -> None:
    pixels = fixture_pixels(A_FRONT) if source == "synthetic" else portrait_pixels()
    points = landmarks_of(face_geometry, pixels)
    span = float(np.linalg.norm(points[33] - points[263]))
    cheek = tuple(int(c) for c in pixels[int(points[205][1]), int(points[205][0])])
    covered = cover(pixels, points, MOUTH_POINTS, cheek, 0.2 * span, 0.22 * span)
    assert run(face_geometry, catalog, limits, covered) == [PhotoReason.MOUTH_COVERED]


# --- Thresholds come from configuration (AC5.5.3) ------------------------------------------------


def test_thresholds_are_read_from_settings() -> None:
    settings = make_settings(
        PHOTO_MIN_WIDTH=700,
        PHOTO_MIN_HEIGHT=900,
        PHOTO_MIN_BRIGHTNESS=10,
        PHOTO_MAX_BRIGHTNESS=250,
        PHOTO_MIN_FACE_FRACTION=0.01,
        PHOTO_MAX_FACE_FRACTION=0.9,
        PHOTO_OCCLUSION_DARK_RATIO=0.2,
        PHOTO_OCCLUSION_MIN_CONTRAST=0.03,
    )
    assert CheckThresholds.from_settings(settings) == CheckThresholds(
        700, 900, 10.0, 250.0, 0.01, 0.9, 0.2, 0.03
    )


def test_a_changed_resolution_threshold_applies_without_code_changes(
    face_geometry: FaceGeometry,  # noqa: F811
    catalog: PhotoCatalog,
) -> None:
    stricter = CheckThresholds.from_settings(make_settings(PHOTO_MIN_WIDTH=1000))
    assert run(face_geometry, catalog, stricter, fixture_pixels(A_FRONT)) == [PhotoReason.TOO_SMALL]


def test_a_changed_pose_range_applies_without_code_changes(
    face_geometry: FaceGeometry,  # noqa: F811
    limits: CheckThresholds,
) -> None:
    widened = load_catalog(DEFAULT_CATALOG_FILE, ["front", "left_3q"], {"left_3q": (-60.0, 15.0)})
    assert run(face_geometry, widened, limits, fixture_pixels(A_FRONT), "left_3q") == []


def test_luminance_weights() -> None:
    pixels = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
    assert luminance(pixels)[0].tolist() == pytest.approx([76.245, 149.685, 29.07])
