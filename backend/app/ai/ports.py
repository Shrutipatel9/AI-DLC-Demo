"""The AI ports (contract C10 ``TextModel`` and ``ImageEditor``).

Every implementation has a timeout and raises a typed :mod:`app.ai.errors` error; each has a
test fake in :mod:`app.ai.fakes`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ImageInput:
    """An image sent to a vendor.

    Attributes:
        data: Encoded image bytes (PNG or JPEG).
        content_type: ``image/png`` or ``image/jpeg``.
        label: A short, non-personal label (``front``, ``left_3q``) the prompt can refer to.
    """

    data: bytes
    content_type: str
    label: str


@dataclass(frozen=True)
class TextMessage:
    """One chat message."""

    role: Literal["system", "user", "assistant"]
    content: str


class TextModel(Protocol):
    """Text (and vision) generation."""

    def generate_structured(
        self,
        messages: Sequence[TextMessage],
        images: Sequence[ImageInput],
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """A JSON object that follows ``json_schema``.

        Raises:
            AiError: A typed vendor failure (rate limit, timeout, unavailable, bad output).
        """
        ...

    def chat(self, messages: Sequence[TextMessage]) -> str:
        """A plain-text reply (the Beauty Assistant, U9).

        Raises:
            AiError: A typed vendor failure.
        """
        ...


class ImageEditor(Protocol):
    """Image editing (the healthy-aging, hairstyle, outfit and after images; U7)."""

    def edit(self, source: ImageInput, instruction: str, fidelity: str) -> bytes:
        """PNG bytes of ``source`` edited as ``instruction`` says.

        Raises:
            AiError: A typed vendor failure.
        """
        ...
