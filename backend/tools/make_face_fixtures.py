"""Render the synthetic face fixtures used by the backend tests and the browser journey.

    uv run python -m tools.make_face_fixtures --out tests/fixtures/faces [--out DIR ...]

[Decided by delivery team] No real person's photo is committed. The faces are rendered from
MediaPipe's canonical face mesh, which ships inside the pinned model bundle
(``geometry_pipeline_metadata_landmarks.binarypb``, Apache-2.0), with flat shading on a
plain white background. The real MediaPipe model detects these renders, including the 3/4
turns, so the tests exercise the real model.

Writes into every ``--out`` directory:

- ``person-a-front.png``, ``person-a-left.png``, ``person-a-right.png``: one synthetic person
  at the three default angles (same-person distances 0.15-0.36, below the 0.6 threshold);
- ``person-b-left.png``: a visibly different face geometry, turned left;
- ``no-face.png``: the white background with a plain shape and no face;

and into the FIRST ``--out`` directory only:

- ``overrides.json``: landmark overrides for ``person-b-left.png`` (see
  ``app.face.overrides``). MediaPipe pulls synthetic faces towards an average face, so a
  synthetic "different person" never scores above the threshold on its own; the override
  widens its mouth, jaw and face so the same-person check sees a different person.

The output is deterministic. Run it again only when the renderer or the model pin changes.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw

from app.face.public import FaceFound, MediaPipeFaceGeometry, pixel_hash

MESH_MEMBER = "geometry_pipeline_metadata_landmarks.binarypb"
WIDTH, HEIGHT, SCALE = 640, 800, 20.0
BACKGROUND = (246, 246, 243)
SKIN = np.array([224, 182, 150], dtype=np.float64)
LIPS_COLOUR = np.array([170, 80, 80], dtype=np.float64)
EYES_COLOUR = np.array([60, 45, 40], dtype=np.float64)
LIGHT = np.array([0.3, 0.4, 1.0]) / np.linalg.norm([0.3, 0.4, 1.0])

OUTER_LIPS = (61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39)
INNER_LIPS = (78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81)
LIPS = frozenset((*OUTER_LIPS, 40, 185, *INNER_LIPS, 80, 191))
EYE_A = (33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246)
EYE_B = (362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398)
EYES = frozenset((*EYE_A, *EYE_B))
#: Landmarks widened for the person-B override: mouth corners, jaw and face edges.
WIDEN = (61, 291, 172, 397, 234, 454)
WIDEN_FACTOR = 1.3


def _varint(data: bytes, index: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        byte = data[index]
        index += 1
        result |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            return result, index


def _fields(data: bytes) -> Iterator[tuple[int, Any]]:
    """A minimal protobuf wire-format reader (varint, 32-bit and length-delimited fields)."""
    index = 0
    while index < len(data):
        key, index = _varint(data, index)
        field, wire = key >> 3, key & 7
        if wire == 0:
            value, index = _varint(data, index)
            yield field, value
        elif wire == 2:
            size, index = _varint(data, index)
            yield field, data[index : index + size]
            index += size
        elif wire == 5:
            yield field, struct.unpack("<f", data[index : index + 4])[0]
            index += 4
        elif wire == 1:
            index += 8
        else:  # pragma: no cover - not used by this message
            raise ValueError(f"unsupported wire type {wire}")


def canonical_mesh(model_path: Path) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """The canonical face mesh: 468 vertices ``(x, y, z)`` and the triangle indices."""
    raw = zipfile.ZipFile(model_path).read(MESH_MEMBER)
    mesh = next(value for field, value in _fields(raw) if field == 1)
    floats: list[float] = []
    indices: list[int] = []
    for field, value in _fields(mesh):
        if field == 3:
            floats.append(value)
        elif field == 4:
            indices.append(value)
    vertices = np.asarray(floats, dtype=np.float64).reshape(-1, 5)[:, :3]
    return vertices, np.asarray(indices, dtype=np.int64).reshape(-1, 3)


def variant(vertices: NDArray[np.float64]) -> NDArray[np.float64]:
    """A visibly different geometry: wider face, mouth and jaw, eyes slightly closer."""
    shaped = vertices.copy()
    for vertex in shaped:
        x, y, _ = vertex
        if 0.8 < y < 4.2 and abs(x) < 5.6:
            vertex[0] *= 0.85
        if abs(x) > 4.0:
            vertex[0] *= 1.2
        if -6 < y < -3.0 and abs(x) < 3.5:
            vertex[0] *= 1.5
        if y < -4.5 and abs(x) > 3:
            vertex[0] *= 1.2
    return shaped


def render(vertices: NDArray[np.float64], triangles: NDArray[np.int64], yaw: float) -> Image.Image:
    """Flat-shaded orthographic render of the mesh turned by ``yaw`` degrees.

    Negative ``yaw`` turns the nose to the image's left (the left cheek faces the camera).
    """
    angle = math.radians(yaw)
    rotation = np.array(
        [
            [math.cos(angle), 0, math.sin(angle)],
            [0, 1, 0],
            [-math.sin(angle), 0, math.cos(angle)],
        ]
    )
    turned = vertices @ rotation.T
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    centre_x, centre_y = WIDTH / 2, HEIGHT * 0.47
    points = np.stack([centre_x + SCALE * turned[:, 0], centre_y - SCALE * turned[:, 1]], axis=1)
    for index in np.argsort([turned[t, 2].mean() for t in triangles]):
        triangle = triangles[index]
        corners = turned[triangle]
        normal = np.cross(corners[1] - corners[0], corners[2] - corners[0])
        length = float(np.linalg.norm(normal))
        if length == 0:
            continue
        normal = normal / length
        if normal[2] < 0:
            normal = -normal
        shade = 0.35 + 0.65 * max(0.0, float(normal @ LIGHT))
        colour = SKIN
        if all(int(v) in LIPS for v in triangle):
            colour = LIPS_COLOUR
        if all(int(v) in EYES for v in triangle):
            colour = EYES_COLOUR
        fill = tuple(int(min(255.0, channel * shade)) for channel in colour)
        draw.polygon([(float(points[v][0]), float(points[v][1])) for v in triangle], fill=fill)
    return image


def no_face() -> Image.Image:
    """The background with a plain grey ellipse and no face."""
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    ImageDraw.Draw(image).ellipse((200, 220, 440, 560), fill=(150, 150, 150))
    return image


def widened(found: FaceFound) -> list[list[float]]:
    """Person-B override: the detected landmarks with mouth, jaw and face edges widened."""
    points = [list(point) for point in found.landmarks]
    centre = (points[234][0] + points[454][0]) / 2
    for index in WIDEN:
        points[index][0] = centre + (points[index][0] - centre) * WIDEN_FACTOR
    return points


def main(argv: list[str] | None = None) -> int:
    """Render the fixtures into every ``--out`` directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, action="append", required=True)
    parser.add_argument("--model", type=Path, default=Path("var/models/face_landmarker.task"))
    args = parser.parse_args(argv)

    vertices, triangles = canonical_mesh(args.model)
    images = {
        "person-a-front.png": render(vertices, triangles, 0),
        "person-a-left.png": render(vertices, triangles, -40),
        "person-a-right.png": render(vertices, triangles, 40),
        "person-b-left.png": render(variant(vertices), triangles, -40),
        "no-face.png": no_face(),
    }
    geometry = MediaPipeFaceGeometry(args.model)
    b_left = np.asarray(images["person-b-left.png"], dtype=np.uint8)
    a_left = geometry.detect(np.asarray(images["person-a-left.png"], dtype=np.uint8))
    if not isinstance(a_left, FaceFound):
        raise SystemExit("the model did not find the person-A left face")
    # B's override starts from A-left's landmarks, so B-left passes the per-photo checks
    # (the pose and the face box stay realistic) while its signature is clearly different.
    overrides = {
        "version": 1,
        "images": {
            pixel_hash(b_left): {"landmarks": widened(a_left), "yawDegrees": a_left.yaw_degrees}
        },
    }
    for out in args.out:
        out.mkdir(parents=True, exist_ok=True)
        for name, image in images.items():
            image.save(out / name, format="PNG", optimize=True)
        print(f"wrote {len(images)} images to {out}")
    first = args.out[0] / "overrides.json"
    first.write_text(json.dumps(overrides, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"wrote {first}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
