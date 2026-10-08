"""Test fakes of the AI ports (AC1.12.3).

They record their calls and can be told to succeed, fail, return malformed output or be slow.
They never touch the network.

A fake is only ever selected in development and test (settings refuse it elsewhere).

- ``FakeTextModel`` answers through a ``responder`` (the report-writing module supplies one
  that returns a valid report), after the behaviours queued with ``fail_next``,
  ``malformed_next`` and ``slow_next``.
- The committed "realistic latency" profile (``data/realistic_latency_v1.json``) gives each
  call a delay; tests inject a virtual ``sleep`` to check the whole run fits NFR4's 10 minutes
  (AC7.2.5) without waiting.
- ``control_dir`` lets a separate worker process be told to fail: a ``fail-text`` file holds
  the number of text calls that must fail; each failing call decrements it (browser journeys).
  A ``fail-image`` file does the same for image calls.
"""

from __future__ import annotations

import io
import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image

from app.ai.errors import AiError, AiUnavailableError
from app.ai.ports import ImageInput, TextMessage

logger = logging.getLogger("ai")

PROFILE_FILE = Path(__file__).parent / "data" / "realistic_latency_v1.json"
FAIL_TEXT_FILE = "fail-text"
FAIL_IMAGE_FILE = "fail-image"

Responder = Callable[[Sequence[TextMessage], Sequence[ImageInput], dict[str, Any]], dict[str, Any]]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class LatencyProfile:
    """Seconds each fake call takes."""

    text_seconds: float = 0.0
    image_seconds: float = 0.0


def load_latency_profile(path: Path = PROFILE_FILE) -> LatencyProfile:
    """The committed realistic latency profile (AC7.2.5)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return LatencyProfile(
        text_seconds=float(data["textSeconds"]), image_seconds=float(data["imageSeconds"])
    )


@dataclass(frozen=True)
class RecordedTextCall:
    """What a fake text call received (photos reduced to label and size)."""

    kind: str
    messages: tuple[TextMessage, ...]
    images: tuple[tuple[str, int], ...]
    schema: dict[str, Any] | None


@dataclass(frozen=True)
class RecordedImageCall:
    """What a fake image call received."""

    label: str
    instruction: str
    fidelity: str
    source_bytes: int


@dataclass
class _Behaviour:
    error: AiError | None = None
    payload: dict[str, Any] | None = None
    delay: float = 0.0


@dataclass
class _Scripted:
    """A queue of one-shot behaviours shared by both fakes."""

    queue: deque[_Behaviour] = field(default_factory=deque)

    def fail_next(self, error: AiError, times: int = 1) -> None:
        """The next ``times`` calls raise ``error``."""
        self.queue.extend(_Behaviour(error=error) for _ in range(times))

    def slow_next(self, seconds: float, times: int = 1) -> None:
        """The next ``times`` calls take ``seconds`` longer, then succeed."""
        self.queue.extend(_Behaviour(delay=seconds) for _ in range(times))


class FakeTextModel:
    """A recording ``TextModel``.

    Args:
        responder: Builds the structured answer when no behaviour is queued.
        profile: Delay of every call (instant by default).
        sleep: Called with each delay; tests pass a virtual clock's ``sleep``.
        control_dir: Optional directory holding a ``fail-text`` count (see module docs).
        extra_delay_seconds: Added to every call's delay.
    """

    def __init__(
        self,
        responder: Responder | None = None,
        *,
        profile: LatencyProfile | None = None,
        sleep: Sleeper = time.sleep,
        control_dir: Path | None = None,
        extra_delay_seconds: float = 0.0,
    ) -> None:
        self._responder = responder or (lambda _m, _i, _s: {})
        self._profile = profile or LatencyProfile()
        self._sleep = sleep
        self._control_dir = control_dir
        self._extra_delay = extra_delay_seconds
        self._script = _Scripted()
        self.calls: list[RecordedTextCall] = []

    def fail_next(self, error: AiError | None = None, times: int = 1) -> None:
        """The next ``times`` calls raise ``error`` (``AiUnavailableError`` by default)."""
        self._script.fail_next(error or AiUnavailableError("fake failure"), times)

    def malformed_next(self, payload: dict[str, Any], times: int = 1) -> None:
        """The next ``times`` structured calls answer ``payload`` instead of a valid report."""
        self._script.queue.extend(_Behaviour(payload=payload) for _ in range(times))

    def slow_next(self, seconds: float, times: int = 1) -> None:
        """The next ``times`` calls take ``seconds`` longer."""
        self._script.slow_next(seconds, times)

    def generate_structured(
        self,
        messages: Sequence[TextMessage],
        images: Sequence[ImageInput],
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """Record the call, then follow the queued behaviour or the responder."""
        self.calls.append(
            RecordedTextCall(
                "structured",
                tuple(messages),
                tuple((image.label, len(image.data)) for image in images),
                json_schema,
            )
        )
        behaviour = self._before_call()
        if behaviour.payload is not None:
            return behaviour.payload
        return self._responder(messages, images, json_schema)

    def chat(self, messages: Sequence[TextMessage]) -> str:
        """Record the call and answer a fixed line."""
        self.calls.append(RecordedTextCall("chat", tuple(messages), (), None))
        self._before_call()
        return "This is a fake assistant reply."

    def _before_call(self) -> _Behaviour:
        behaviour = self._script.queue.popleft() if self._script.queue else _Behaviour()
        delay = self._profile.text_seconds + self._extra_delay + behaviour.delay
        if delay > 0:
            self._sleep(delay)
        if behaviour.error is not None:
            raise behaviour.error
        self._consume_control_failure()
        return behaviour

    def _consume_control_failure(self) -> None:
        if _consume_marker(self._control_dir, FAIL_TEXT_FILE):
            raise AiUnavailableError("fake failure injected by the control file")


def _consume_marker(control_dir: Path | None, name: str) -> bool:
    """Decrement a control file's count; True when this call must fail."""
    if control_dir is None:
        return False
    marker = control_dir / name
    try:
        remaining = int(marker.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return False
    if remaining <= 0:
        return False
    marker.write_text(str(remaining - 1), encoding="utf-8")
    logger.info("fake failure injected", extra={"event": "ai.fake.failure"})
    return True


def _tiny_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (128, 128, 128)).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeImageEditor:
    """A recording ``ImageEditor`` that returns a small grey PNG.

    Args:
        profile: Delay of every call (instant by default).
        sleep: Called with each delay.
        control_dir: Optional directory holding a ``fail-image`` count (see module docs).
    """

    def __init__(
        self,
        *,
        profile: LatencyProfile | None = None,
        sleep: Sleeper = time.sleep,
        control_dir: Path | None = None,
    ) -> None:
        self._profile = profile or LatencyProfile()
        self._sleep = sleep
        self._control_dir = control_dir
        self._lock = threading.Lock()  # image slots are generated concurrently
        self._script = _Scripted()
        self._image = _tiny_png()
        self.calls: list[RecordedImageCall] = []

    def fail_next(self, error: AiError | None = None, times: int = 1) -> None:
        """The next ``times`` calls raise ``error`` (``AiUnavailableError`` by default)."""
        self._script.fail_next(error or AiUnavailableError("fake failure"), times)

    def malformed_next(self, times: int = 1) -> None:
        """The next ``times`` calls return bytes that are not an image."""
        self._script.queue.extend(_Behaviour(payload={}) for _ in range(times))

    def slow_next(self, seconds: float, times: int = 1) -> None:
        """The next ``times`` calls take ``seconds`` longer."""
        self._script.slow_next(seconds, times)

    def edit(self, source: ImageInput, instruction: str, fidelity: str) -> bytes:
        """Record the call, then follow the queued behaviour."""
        self.calls.append(RecordedImageCall(source.label, instruction, fidelity, len(source.data)))
        with self._lock:
            behaviour = self._script.queue.popleft() if self._script.queue else _Behaviour()
            injected = behaviour.error is None and _consume_marker(
                self._control_dir, FAIL_IMAGE_FILE
            )
        delay = self._profile.image_seconds + behaviour.delay
        if delay > 0:
            self._sleep(delay)
        if behaviour.error is not None:
            raise behaviour.error
        if injected:
            raise AiUnavailableError("fake failure injected by the control file")
        if behaviour.payload is not None:
            return b"not an image"
        return self._image
