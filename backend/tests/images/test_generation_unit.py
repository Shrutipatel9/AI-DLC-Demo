"""Image generation details that need no database rows: concurrency and the migration."""

from __future__ import annotations

import threading
import uuid
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect

from alembic import command
from app.analysis.public import RunContext
from app.images import service as images_service
from app.images.catalog import PromptSpec
from app.images.public import ImageGenerationService
from app.platform.clock import FrozenClock
from tests.conftest import FROZEN_START, alembic_config
from tests.platform.test_db_and_migrations import scratch_database  # noqa: F401  (fixture)

CLOCK = FrozenClock(FROZEN_START)


class _Generator:
    """Records how many slots are generated at once; a barrier proves they overlap."""

    def __init__(self, parties: int) -> None:
        self.barrier = threading.Barrier(parties, timeout=5)
        self.lock = threading.Lock()
        self.in_flight = 0
        self.peak = 0

    def generate(self, user_id: uuid.UUID, source: Any, spec: PromptSpec) -> tuple[uuid.UUID, int]:
        with self.lock:
            self.in_flight += 1
            self.peak = max(self.peak, self.in_flight)
        self.barrier.wait()
        with self.lock:
            self.in_flight -= 1
        return uuid.uuid4(), 1


class _Media:
    def get(self, *_a: Any, **_k: Any) -> Any:
        return type("Stored", (), {"data": b"x", "content_type": "image/png"})()


class _Session:
    def __enter__(self) -> _Session:
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None

    def commit(self) -> None:
        return None


def _service(generator: Any, concurrency: int) -> ImageGenerationService:
    return ImageGenerationService(
        generator=generator,
        media=_Media(),  # type: ignore[arg-type]
        session_factory=_Session,  # type: ignore[arg-type]
        clock=CLOCK,
        concurrency=concurrency,
        manual_limit=3,
    )


@pytest.mark.parametrize("concurrency", [2, 4])
def test_images_are_generated_with_the_configured_concurrency(
    monkeypatch: pytest.MonkeyPatch, concurrency: int
) -> None:
    """AC7.6.4: up to ``AI_IMAGE_CONCURRENCY`` images at once, never more."""
    generator = _Generator(concurrency)
    pending = [f"slot_{n}" for n in range(concurrency * 3)]
    recorded: list[str] = []
    monkeypatch.setattr(images_service, "ensure_slots", lambda *a, **k: None)
    monkeypatch.setattr(
        images_service,
        "list_slot_views",
        lambda *a, **k: [
            type("View", (), {"slot_key": key, "status": "pending"})() for key in pending
        ],
    )
    monkeypatch.setattr(
        images_service, "spec_for", lambda key: PromptSpec(key, "feature", key, key)
    )
    monkeypatch.setattr(
        images_service, "record_auto_result", lambda _s, _r, key, **_k: recorded.append(key)
    )
    ctx = RunContext(uuid.uuid4(), uuid.uuid4(), {"front": uuid.uuid4()}, {}, _Session)  # type: ignore[arg-type]

    result = _service(generator, concurrency).generate_step(ctx)

    assert result.status == "done"
    assert result.output["ready"] == len(pending)
    assert generator.peak == concurrency
    assert sorted(recorded) == sorted(pending)


def test_a_run_without_a_front_photo_fails_the_step_without_a_vendor_call() -> None:
    generator = _Generator(1)
    ctx = RunContext(uuid.uuid4(), uuid.uuid4(), {}, {}, _Session)  # type: ignore[arg-type]

    assert _service(generator, 1).generate_step(ctx).status == "failed"
    assert generator.peak == 0


def test_0007_upgrades_and_downgrades_cleanly(scratch_database: str) -> None:  # noqa: F811
    cfg = alembic_config(scratch_database)
    engine = create_engine(scratch_database)
    try:
        command.upgrade(cfg, "0007_u7_images")
        inspector = inspect(engine)
        columns = {c["name"] for c in inspector.get_columns("analysis_image_slots")}
        assert {"media_file_id", "auto_attempts", "manual_retries", "updated_at"} <= columns
        kinds = [c["sqltext"] for c in inspector.get_check_constraints("media_files")]
        assert any("ai_image" in text for text in kinds)

        command.downgrade(cfg, "0006_u6_analysis")
        columns = {c["name"] for c in inspect(engine).get_columns("analysis_image_slots")}
        assert "media_file_id" not in columns
        command.upgrade(cfg, "head")
    finally:
        engine.dispose()
