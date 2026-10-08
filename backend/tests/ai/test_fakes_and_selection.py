"""The AI fakes and the configuration-driven adapter choice (AC1.12.1, AC1.12.3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.ai.errors import AiRateLimitError, AiUnavailableError
from app.ai.fakes import FAIL_TEXT_FILE, FakeImageEditor, FakeTextModel, LatencyProfile
from app.ai.openai_image import OpenAiImageEditor
from app.ai.openai_text import OpenAiTextModel
from app.ai.ports import ImageInput, TextMessage
from app.ai.public import build_image_editor, build_text_model, load_latency_profile
from tests.helpers import make_settings

PHOTO = ImageInput(b"photo-bytes", "image/png", "front")


class VirtualSleep:
    """Records delays instead of waiting."""

    def __init__(self) -> None:
        self.total = 0.0

    def __call__(self, seconds: float) -> None:
        self.total += seconds


def test_tests_resolve_both_adapters_to_fakes() -> None:
    settings = make_settings()
    assert isinstance(build_text_model(settings), FakeTextModel)
    assert isinstance(build_image_editor(settings), FakeImageEditor)


def test_the_openai_adapters_are_chosen_by_configuration_alone() -> None:
    """AC1.12.1: only settings change which adapter answers; no calling code changes."""
    settings = make_settings(
        AI_TEXT_PROVIDER="openai",
        AI_IMAGE_PROVIDER="openai",
        OPENAI_API_KEY="sk-test-not-real",
        OPENAI_TEXT_MODEL="text-model-x",
        OPENAI_IMAGE_MODEL="image-model-y",
        OPENAI_BASE_URL="https://vendor.example.test/v1/",
    )
    assert isinstance(build_text_model(settings), OpenAiTextModel)
    editor = build_image_editor(settings)
    assert isinstance(editor, OpenAiImageEditor)
    assert settings.openai_base_url == "https://vendor.example.test/v1"


def test_the_image_vendor_can_differ_from_the_text_vendor() -> None:
    settings = make_settings(
        AI_IMAGE_PROVIDER="openai", OPENAI_API_KEY="sk-test-not-real", OPENAI_IMAGE_MODEL="img"
    )
    assert isinstance(build_text_model(settings), FakeTextModel)
    assert isinstance(build_image_editor(settings), OpenAiImageEditor)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"AI_TEXT_PROVIDER": "openai", "OPENAI_TEXT_MODEL": "m"}, "OPENAI_API_KEY"),
        ({"AI_TEXT_PROVIDER": "openai", "OPENAI_API_KEY": "k"}, "OPENAI_TEXT_MODEL"),
        ({"AI_IMAGE_PROVIDER": "openai", "OPENAI_API_KEY": "k"}, "OPENAI_IMAGE_MODEL"),
        ({"APP_ENV": "production", "AI_TEXT_PROVIDER": "fake"}, "only allowed"),
        ({"OPENAI_BASE_URL": "ftp://nope"}, "OPENAI_BASE_URL"),
        ({"SYMMETRY_LABEL_BANDS": '{"High": 50}'}, "SYMMETRY_LABEL_BANDS"),
        ({"WORKER_HEARTBEAT_SECONDS": 90}, "WORKER_STALE_AFTER_SECONDS"),
    ],
)
def test_unsafe_ai_configuration_stops_start_up_naming_the_setting(
    overrides: dict[str, Any], message: str
) -> None:
    with pytest.raises((ValidationError, ValueError), match=message):
        make_settings(**overrides)


def test_the_fake_text_model_records_what_it_was_sent() -> None:
    fake = FakeTextModel(lambda _m, _i, _s: {"ok": True})
    out = fake.generate_structured([TextMessage("user", "hello")], [PHOTO], {"type": "object"})

    assert out == {"ok": True}
    call = fake.calls[0]
    assert call.kind == "structured"
    assert call.messages[0].content == "hello"
    assert call.images == (("front", len(PHOTO.data)),)  # label and size, never the bytes
    fake.chat([TextMessage("user", "hi")])
    assert fake.calls[1].kind == "chat"


def test_the_fake_text_model_can_succeed_fail_return_malformed_output_or_be_slow() -> None:
    sleeper = VirtualSleep()
    fake = FakeTextModel(lambda _m, _i, _s: {"ok": True}, sleep=sleeper)
    fake.fail_next(times=1)
    fake.fail_next(AiRateLimitError(retry_after=3))
    fake.malformed_next({"features": "oops"})
    fake.slow_next(25)

    with pytest.raises(AiUnavailableError):
        fake.generate_structured([], [], {})
    with pytest.raises(AiRateLimitError):
        fake.generate_structured([], [], {})
    assert fake.generate_structured([], [], {}) == {"features": "oops"}
    assert fake.generate_structured([], [], {}) == {"ok": True}
    assert sleeper.total == 25
    assert fake.generate_structured([], [], {}) == {"ok": True}  # queue is used up
    assert len(fake.calls) == 5


def test_a_control_file_makes_a_separate_process_fail_a_set_number_of_calls(
    tmp_path: Path,
) -> None:
    (tmp_path / FAIL_TEXT_FILE).write_text("2", encoding="utf-8")
    fake = FakeTextModel(lambda _m, _i, _s: {"ok": True}, control_dir=tmp_path)

    for _ in range(2):
        with pytest.raises(AiUnavailableError):
            fake.generate_structured([], [], {})
    assert fake.generate_structured([], [], {}) == {"ok": True}
    assert (tmp_path / FAIL_TEXT_FILE).read_text(encoding="utf-8") == "0"

    (tmp_path / FAIL_TEXT_FILE).write_text("not a number", encoding="utf-8")
    assert fake.generate_structured([], [], {}) == {"ok": True}


def test_the_fake_image_editor_records_and_can_fail_be_malformed_or_slow() -> None:
    sleeper = VirtualSleep()
    fake = FakeImageEditor(profile=LatencyProfile(image_seconds=2), sleep=sleeper)
    fake.fail_next()
    fake.malformed_next()
    fake.slow_next(10)

    with pytest.raises(AiUnavailableError):
        fake.edit(PHOTO, "older", "high")
    assert fake.edit(PHOTO, "older", "high") == b"not an image"
    ok = fake.edit(PHOTO, "older", "high")
    assert ok.startswith(b"\x89PNG")
    assert sleeper.total == 2 * 3 + 10
    assert [c.instruction for c in fake.calls] == ["older"] * 3
    assert fake.calls[0].source_bytes == len(PHOTO.data)


def test_the_committed_realistic_latency_profile_loads() -> None:
    profile = load_latency_profile()
    assert profile.text_seconds > 0
    assert profile.image_seconds > 0
    realistic = make_settings(AI_FAKE_PROFILE="realistic")
    sleeper = VirtualSleep()
    model = build_text_model(realistic, sleep=sleeper)
    model.chat([TextMessage("user", "hi")])
    assert sleeper.total == profile.text_seconds
