"""Migration 0008 (the cached report PDF) and the scoring helpers."""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from alembic import command
from app.measurement.public import attribute_phrase, feature_scores
from tests.conftest import alembic_config
from tests.platform.test_db_and_migrations import scratch_database  # noqa: F401  (fixture)


def test_0008_upgrades_and_downgrades_cleanly(scratch_database: str) -> None:  # noqa: F811
    cfg = alembic_config(scratch_database)
    engine = create_engine(scratch_database)
    try:
        command.upgrade(cfg, "0008_u8_report")
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("report_pdfs")}
        assert {"run_id", "user_id", "media_file_id", "fingerprint", "created_at"} <= columns
        kinds = [c["sqltext"] for c in inspector.get_check_constraints("media_files")]
        assert any("report_pdf" in text for text in kinds)

        command.downgrade(cfg, "0007_u7_images")
        assert "report_pdfs" not in inspect(engine).get_table_names()
        command.upgrade(cfg, "head")
    finally:
        engine.dispose()


def test_feature_scores_compare_to_the_reference_and_never_invent_a_zero() -> None:
    features = {
        "jaw": {"measured": True, "values": {"jaw_width_ratio": 0.82}},
        "nose": {"measured": True, "values": {"nose_width_ratio": 0.50}},
        "hair": {"measured": False, "values": {}},
        "skin": {"measured": True, "values": {"skin_tone_evenness": 64.4}},
    }

    scores = feature_scores(features)

    assert scores["jaw"] == 100  # exactly the reference mean
    assert scores["nose"] is not None
    assert scores["nose"] < 5
    assert scores["hair"] is None
    assert scores["skin"] == 64


def test_attribute_phrases() -> None:
    assert attribute_phrase("jaw_width_ratio", 0.82) == "within the typical range"
    assert attribute_phrase("jaw_width_ratio", 0.99) == "wider or larger than typical"
    assert attribute_phrase("jaw_width_ratio", 0.60) == "narrower or smaller than typical"
