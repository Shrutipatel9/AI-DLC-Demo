"""The photo catalog: requirement rules, capture guidance and the angle definitions.

The bundled ``data/catalog_v1.json`` follows [PC] §1-§3. ``PHOTO_ANGLES`` chooses which
catalog angles are required and in which order, so changing the angle set is a
configuration change (ASM-005, AC5.2.1). ``PHOTO_POSE_YAW_RANGES`` can override an angle's
pose range without editing the file (AC5.5.3). The catalog is validated at start-up, so a
bad file or an unknown angle stops the process instead of failing a request.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

DEFAULT_CATALOG_FILE = Path(__file__).resolve().parent / "data" / "catalog_v1.json"

Illustration = Literal["front", "left", "right"]
_ILLUSTRATIONS: frozenset[str] = frozenset({"front", "left", "right"})


class CatalogError(ValueError):
    """The catalog file is missing or invalid, or a configured angle is not in it."""


@dataclass(frozen=True)
class PhotoRule:
    """One of the requirement rules shown before capture (FR-005)."""

    id: str
    text: str


@dataclass(frozen=True)
class AngleSpec:
    """One required angle.

    Attributes:
        yaw_min: Lowest accepted head yaw in degrees (see ``FaceFound.yaw_degrees``).
        yaw_max: Highest accepted head yaw in degrees.
    """

    id: str
    label: str
    instruction: str
    turn_hint: str
    illustration: Illustration
    yaw_min: float
    yaw_max: float


@dataclass(frozen=True)
class PhotoCatalog:
    """The validated catalog restricted to the configured angles (in configured order)."""

    version: str
    rules: tuple[PhotoRule, ...]
    guidance: tuple[str, ...]
    angles: tuple[AngleSpec, ...]

    @property
    def angle_ids(self) -> list[str]:
        """The required angle ids, in order."""
        return [angle.id for angle in self.angles]

    def angle(self, angle_id: str) -> AngleSpec | None:
        """The configured angle with this id, if any."""
        return next((angle for angle in self.angles if angle.id == angle_id), None)


def _text(entry: Mapping[str, Any], key: str, where: str) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CatalogError(f"{where}: '{key}' must be non-empty text")
    return value.strip()


def _angle(entry: Any, overrides: Mapping[str, tuple[float, float]]) -> AngleSpec:
    if not isinstance(entry, dict):
        raise CatalogError("each angle must be an object")
    angle_id = _text(entry, "id", "angle")
    where = f"angle {angle_id}"
    illustration = _text(entry, "illustration", where)
    if illustration not in _ILLUSTRATIONS:
        raise CatalogError(f"{where}: illustration must be front, left or right")
    raw_range = entry.get("yawRange")
    if (
        not isinstance(raw_range, list)
        or len(raw_range) != 2
        or not all(isinstance(v, int | float) and not isinstance(v, bool) for v in raw_range)
        or not -90 <= raw_range[0] < raw_range[1] <= 90
    ):
        raise CatalogError(f"{where}: yawRange must be [min, max] within -90..90")
    yaw_min, yaw_max = overrides.get(angle_id, (float(raw_range[0]), float(raw_range[1])))
    return AngleSpec(
        id=angle_id,
        label=_text(entry, "label", where),
        instruction=_text(entry, "instruction", where),
        turn_hint=_text(entry, "turnHint", where),
        illustration=cast(Illustration, illustration),  # checked above
        yaw_min=yaw_min,
        yaw_max=yaw_max,
    )


def load_catalog(
    path: Path,
    required_angles: Sequence[str],
    yaw_overrides: Mapping[str, tuple[float, float]] | None = None,
) -> PhotoCatalog:
    """Load the catalog and keep the configured angles, in configured order.

    Raises:
        CatalogError: When the file is unreadable or invalid, when a configured angle (or a
            yaw override) names an angle the catalog lacks.
    """
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"cannot read the photo catalog at {path}") from exc
    if not isinstance(data, dict):
        raise CatalogError("the photo catalog must be a JSON object")
    version = _text(data, "version", "catalog")
    raw_rules, raw_guidance, raw_angles = (
        data.get("rules"),
        data.get("guidance"),
        data.get("angles"),
    )
    if not isinstance(raw_rules, list) or not raw_rules:
        raise CatalogError("catalog: 'rules' must be a non-empty list")
    if not isinstance(raw_guidance, list) or not all(isinstance(g, str) for g in raw_guidance):
        raise CatalogError("catalog: 'guidance' must be a list of text")
    if not isinstance(raw_angles, list) or not raw_angles:
        raise CatalogError("catalog: 'angles' must be a non-empty list")
    rules = tuple(
        PhotoRule(id=_text(rule, "id", "rule"), text=_text(rule, "text", "rule"))
        if isinstance(rule, dict)
        else _bad_rule()
        for rule in raw_rules
    )
    overrides = dict(yaw_overrides or {})
    known = {angle.id: angle for angle in (_angle(entry, overrides) for entry in raw_angles)}
    unknown = [angle for angle in [*required_angles, *overrides] if angle not in known]
    if unknown:
        raise CatalogError(f"angles not in the photo catalog: {', '.join(sorted(set(unknown)))}")
    return PhotoCatalog(
        version=version,
        rules=rules,
        guidance=tuple(g.strip() for g in raw_guidance if g.strip()),
        angles=tuple(known[angle_id] for angle_id in required_angles),
    )


def _bad_rule() -> PhotoRule:
    raise CatalogError("each rule must be an object with id and text")
