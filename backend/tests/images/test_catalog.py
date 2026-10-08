"""The prompt catalog (US9.1-US9.4): 24 versioned requests, one per analysis slot."""

from __future__ import annotations

from collections import Counter

from app.analysis.public import SLOT_KINDS
from app.images.catalog import AI_LABEL, CATALOG, CATALOG_VERSION, order_of, spec_for

MEDICAL_WORDS = ("medical", "medication", "allerg", "diagnos", "treat", "disease")


def test_the_catalog_has_a_prompt_for_each_of_the_24_slots_in_order() -> None:
    assert [spec.slot_key for spec in CATALOG] == [key for key, _ in SLOT_KINDS]
    assert len(CATALOG) == 24
    assert CATALOG_VERSION  # versioned seed data (U7 plan Step 2)


def test_groups_are_11_features_5_hairstyles_5_outfits_and_3_aging_cards() -> None:
    counts = Counter(spec.group for spec in CATALOG)
    assert counts == {"feature": 11, "hairstyle": 5, "outfit": 5, "aging": 3}
    assert [s.slot_key for s in CATALOG if s.group == "aging"] == [
        "aging_plus_3",
        "aging_plus_5",
        "aging_plus_10",
    ]


def test_every_instruction_keeps_the_person_and_stays_cosmetic() -> None:
    for spec in CATALOG:
        text = spec.instruction.lower()
        assert "keep their face" in text, spec.slot_key
        assert "identity" in text, spec.slot_key
        assert not any(word in text for word in MEDICAL_WORDS), spec.slot_key
    assert len({spec.instruction for spec in CATALOG}) == 24


def test_lookup_and_label() -> None:
    assert spec_for("hairstyle_1") is not None
    assert spec_for("nope") is None
    assert order_of("hair") == 0
    assert order_of("nope") == 24
    assert AI_LABEL == "AI-generated illustration"
