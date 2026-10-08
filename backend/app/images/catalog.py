"""The versioned prompt catalog for the 24 image slots (US9.1-US9.4).

Every request is an image edit of the user's own front photo, so the result stays them; the
instruction only says what changes. The wording is cosmetic and non-medical (FR-008(f)).
[Decided by delivery team] The client names the counts (11 + 5 + 5 + 3), not the looks; the
hairstyles, outfits and aging wording below are ours and change by bumping ``CATALOG_VERSION``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

CATALOG_VERSION: Final = "u7-v1"

#: Shown with every generated image (AC9.2.1, AC9.3.1, AC9.4.1).
AI_LABEL: Final = "AI-generated illustration"

_KEEP_IDENTITY: Final = (
    "Edit this photo of the person. Keep their face, identity, skin tone, age, expression, "
    "pose and background exactly the same, and keep the photo realistic. Add no text, logos "
    "or watermarks. Change only the following: "
)


@dataclass(frozen=True)
class PromptSpec:
    """One slot's request.

    Attributes:
        slot_key: The slot (``hair``, ``hairstyle_1``, ``aging_plus_3`` ...).
        group: ``feature``, ``hairstyle``, ``outfit`` or ``aging``.
        title: A short plain label for the screen.
        instruction: The full edit instruction sent to the vendor.
    """

    slot_key: str
    group: str
    title: str
    instruction: str


def _spec(slot_key: str, group: str, title: str, change: str) -> PromptSpec:
    return PromptSpec(slot_key, group, title, _KEEP_IDENTITY + change)


_FEATURES: Final = (
    ("hair", "Hair", "make the hair look healthier, fuller and neatly groomed."),
    ("eyebrows", "Eyebrows", "make the eyebrows look neatly shaped and evenly filled."),
    ("eyes", "Eyes", "make the eyes look brighter and more rested, with a refreshed under-eye."),
    ("nose", "Nose", "make the nose area look softly balanced with gentle, natural contouring."),
    ("cheeks", "Cheeks", "give the cheeks a soft, healthy glow with gentle natural contouring."),
    ("jaw", "Jaw", "make the jawline look a little more defined with gentle natural contouring."),
    ("lips", "Lips", "make the lips look smooth, hydrated and evenly toned."),
    ("chin", "Chin", "make the chin look softly balanced with gentle natural contouring."),
    ("skin", "Skin", "make the skin look clearer and evenly toned, keeping natural texture."),
    ("neck", "Neck", "make the neck look smooth and relaxed, with even skin tone."),
    ("ears", "Ears", "make the ears look neat and evenly toned."),
)
_HAIRSTYLES: Final = (
    ("short textured crop", "a short textured crop"),
    ("long soft layers", "long, soft layers past the shoulders"),
    ("side-swept bob", "a chin-length side-swept bob"),
    ("natural curls", "natural, defined curls at medium length"),
    ("tied-back style", "a neat low tied-back style"),
)
_OUTFITS: Final = (
    ("tailored blazer", "a tailored blazer over a plain top"),
    ("crew-neck sweater", "a soft crew-neck knit sweater"),
    ("white shirt", "a crisp white collared shirt"),
    ("denim jacket", "a casual denim jacket over a plain tee"),
    ("evening wear", "smart evening wear with a refined neckline"),
)
_AGING: Final = (3, 5, 10)


def _build() -> tuple[PromptSpec, ...]:
    specs: list[PromptSpec] = [
        _spec(key, "feature", title, change) for key, title, change in _FEATURES
    ]
    specs += [
        _spec(f"hairstyle_{n}", "hairstyle", title.capitalize(), f"give them {change}.")
        for n, (title, change) in enumerate(_HAIRSTYLES, start=1)
    ]
    specs += [
        _spec(f"outfit_{n}", "outfit", title.capitalize(), f"dress them in {change}.")
        for n, (title, change) in enumerate(_OUTFITS, start=1)
    ]
    specs += [
        _spec(
            f"aging_plus_{years}",
            "aging",
            f"In {years} years",
            f"show how they might look {years} years older if they keep up healthy habits "
            "(sun protection, sleep, hydration), aging naturally.",
        )
        for years in _AGING
    ]
    return tuple(specs)


#: The 24 prompts in slot order.
CATALOG: Final = _build()
_BY_KEY: Final = {spec.slot_key: spec for spec in CATALOG}
_ORDER: Final = {spec.slot_key: index for index, spec in enumerate(CATALOG)}


def spec_for(slot_key: str) -> PromptSpec | None:
    """The prompt of a slot, or ``None`` for a key the catalog does not know."""
    return _BY_KEY.get(slot_key)


def order_of(slot_key: str) -> int:
    """The slot's position in the catalog (unknown keys last)."""
    return _ORDER.get(slot_key, len(CATALOG))
