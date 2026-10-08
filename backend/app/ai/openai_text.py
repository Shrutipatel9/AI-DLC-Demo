"""OpenAI text and vision adapter (``TextModel``; FR-008, NFR-008).

Base URL, key and model are configuration values. Photos are sent as ``data:`` URLs in the
chat message, together with the instructions and measurements. Nothing is logged but the
event name (see :mod:`app.ai.openai_http`).
"""

from __future__ import annotations

import base64
import json
from collections.abc import Sequence
from typing import Any

import httpx

from app.ai.errors import AiBadOutputError
from app.ai.openai_http import post
from app.ai.ports import ImageInput, TextMessage

_SCHEMA_NAME = "structured_output"


class OpenAiTextModel:
    """Chat Completions with JSON-schema output.

    Args:
        base_url: The API base URL (``OPENAI_BASE_URL``).
        api_key: The bearer token (``OPENAI_API_KEY``).
        model: The model name (``OPENAI_TEXT_MODEL``).
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
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._client = client or httpx.Client()

    def generate_structured(
        self,
        messages: Sequence[TextMessage],
        images: Sequence[ImageInput],
        json_schema: dict[str, Any],
    ) -> dict[str, Any]:
        """A JSON object that follows ``json_schema`` (see ``TextModel``)."""
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._messages(messages, images),
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": _SCHEMA_NAME, "schema": json_schema, "strict": False},
            },
        }
        text = self._complete(payload)
        try:
            parsed = json.loads(text)
        except ValueError:
            raise AiBadOutputError("The AI service did not return valid JSON.") from None
        if not isinstance(parsed, dict):
            raise AiBadOutputError("The AI service returned JSON that is not an object.")
        return parsed

    def chat(self, messages: Sequence[TextMessage]) -> str:
        """A plain-text reply."""
        return self._complete({"model": self._model, "messages": self._messages(messages, ())})

    def _complete(self, payload: dict[str, Any]) -> str:
        body = post(
            self._client,
            self._url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout_seconds=self._timeout,
            operation="text",
            json=payload,
        )
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise AiBadOutputError("The AI service answered with an unexpected shape.") from None
        if not isinstance(content, str) or not content.strip():
            raise AiBadOutputError("The AI service answered with no text.")
        return content

    @staticmethod
    def _messages(
        messages: Sequence[TextMessage], images: Sequence[ImageInput]
    ) -> list[dict[str, Any]]:
        rendered: list[dict[str, Any]] = [
            {"role": message.role, "content": message.content} for message in messages
        ]
        if images:
            parts: list[dict[str, Any]] = []
            for image in images:
                encoded = base64.b64encode(image.data).decode("ascii")
                parts.append({"type": "text", "text": f"Photo: {image.label}"})
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{image.content_type};base64,{encoded}"},
                    }
                )
            rendered.append({"role": "user", "content": parts})
        return rendered
