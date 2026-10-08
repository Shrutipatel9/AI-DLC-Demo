"""OpenAI image-editing adapter (``ImageEditor``; FR-020, FR-022, NFR-013; used by U7).

The image vendor is a configuration value: a different adapter can replace this one by
setting ``AI_IMAGE_PROVIDER`` and registering it in :mod:`app.ai.public`, with no change
anywhere else (AC1.12.1).
"""

from __future__ import annotations

import base64

import httpx

from app.ai.errors import AiBadOutputError
from app.ai.openai_http import post
from app.ai.ports import ImageInput


class OpenAiImageEditor:
    """``POST /images/edits`` with the source photo and an instruction.

    Args:
        base_url: The API base URL (``OPENAI_BASE_URL``).
        api_key: The bearer token (``OPENAI_API_KEY``).
        model: The image model name (``OPENAI_IMAGE_MODEL``).
        timeout_seconds: Per-call timeout.
        client: HTTP client; created when omitted (tests inject a mock transport).
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/images/edits"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._client = client or httpx.Client()

    def edit(self, source: ImageInput, instruction: str, fidelity: str) -> bytes:
        """PNG bytes of the edited image (see ``ImageEditor``)."""
        body = post(
            self._client,
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout_seconds=self._timeout,
            operation="image",
            data={"model": self._model, "prompt": instruction, "input_fidelity": fidelity},
            files={"image": (f"{source.label}.png", source.data, source.content_type)},
        )
        try:
            encoded = body["data"][0]["b64_json"]
            image = base64.b64decode(encoded, validate=True)
        except (KeyError, IndexError, TypeError, ValueError):
            raise AiBadOutputError("The AI service returned no image.") from None
        if not image:
            raise AiBadOutputError("The AI service returned an empty image.")
        return image
