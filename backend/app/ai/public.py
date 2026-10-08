"""The AI module's public interface (contract C10 ``TextModel`` / ``ImageEditor``).

- ``build_text_model`` / ``build_image_editor``: the adapters chosen by ``AI_TEXT_PROVIDER`` /
  ``AI_IMAGE_PROVIDER`` (``openai`` or ``fake``). Swapping a vendor changes configuration and
  this registry only (AC1.12.1).
- The ports, their message types and the typed vendor errors; the fakes for tests.
"""

from __future__ import annotations

import time
from pathlib import Path

from app.ai.errors import (
    AiBadOutputError,
    AiError,
    AiRateLimitError,
    AiRequestRejectedError,
    AiTimeoutError,
    AiUnavailableError,
)
from app.ai.fakes import (
    FakeImageEditor,
    FakeTextModel,
    LatencyProfile,
    Responder,
    Sleeper,
    load_latency_profile,
)
from app.ai.openai_image import OpenAiImageEditor
from app.ai.openai_text import OpenAiTextModel
from app.ai.ports import ImageEditor, ImageInput, TextMessage, TextModel
from app.platform.settings import Settings

__all__ = [
    "AiBadOutputError",
    "AiError",
    "AiRateLimitError",
    "AiRequestRejectedError",
    "AiTimeoutError",
    "AiUnavailableError",
    "FakeImageEditor",
    "FakeTextModel",
    "ImageEditor",
    "ImageInput",
    "LatencyProfile",
    "Responder",
    "TextMessage",
    "TextModel",
    "build_image_editor",
    "build_text_model",
]


def _profile(settings: Settings) -> LatencyProfile | None:
    return load_latency_profile() if settings.ai_fake_profile == "realistic" else None


def build_text_model(
    settings: Settings,
    *,
    responder: Responder | None = None,
    sleep: Sleeper = time.sleep,
) -> TextModel:
    """The text adapter for ``AI_TEXT_PROVIDER``.

    ``responder`` is only used by the fake: it builds the structured answer (the composition
    root passes the report-writing module's, so this module stays free of report knowledge).
    """
    if settings.ai_text_provider == "fake":
        control: Path | None = settings.ai_fake_control_dir
        return FakeTextModel(
            responder,
            profile=_profile(settings),
            sleep=sleep,
            control_dir=control,
            extra_delay_seconds=settings.ai_fake_text_delay_seconds,
        )
    # Settings guarantee the key and the model for the openai provider.
    assert settings.openai_api_key is not None  # noqa: S101
    assert settings.openai_text_model is not None  # noqa: S101
    return OpenAiTextModel(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_text_model,
        timeout_seconds=settings.ai_text_timeout_seconds,
    )


def build_image_editor(settings: Settings, *, sleep: Sleeper = time.sleep) -> ImageEditor:
    """The image adapter for ``AI_IMAGE_PROVIDER``."""
    if settings.ai_image_provider == "fake":
        return FakeImageEditor(
            profile=_profile(settings), sleep=sleep, control_dir=settings.ai_fake_control_dir
        )
    assert settings.openai_api_key is not None  # noqa: S101
    assert settings.openai_image_model is not None  # noqa: S101
    return OpenAiImageEditor(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.openai_image_model,
        timeout_seconds=settings.ai_image_timeout_seconds,
    )
