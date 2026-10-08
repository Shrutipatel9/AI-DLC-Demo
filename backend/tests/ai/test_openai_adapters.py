"""The OpenAI adapters: configured endpoint, timeouts and typed errors (AC1.12.2).

They run against ``httpx.MockTransport``: no network, no key, no cost (NFR-008).
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.ai.errors import (
    AiBadOutputError,
    AiRateLimitError,
    AiRequestRejectedError,
    AiTimeoutError,
    AiUnavailableError,
)
from app.ai.openai_image import OpenAiImageEditor
from app.ai.openai_text import OpenAiTextModel
from app.ai.ports import ImageInput, TextMessage

BASE = "https://vendor.example.test/v1"
KEY = "sk-test-not-a-real-key"
CANARY = "CANARY-PHOTO-OR-ANSWER-91c2"
SCHEMA: dict[str, Any] = {"type": "object"}


def text_model(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAiTextModel:
    return OpenAiTextModel(
        base_url=BASE,
        api_key=KEY,
        model="configured-text-model",
        timeout_seconds=7.0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def image_editor(handler: Callable[[httpx.Request], httpx.Response]) -> OpenAiImageEditor:
    return OpenAiImageEditor(
        base_url=BASE,
        api_key=KEY,
        model="configured-image-model",
        timeout_seconds=7.0,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_structured_text_uses_the_configured_url_key_model_and_sends_the_photos() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers["Authorization"]
        captured["body"] = json.loads(request.content)
        return reply('{"features": []}')

    photo = ImageInput(b"\x89PNG-bytes", "image/png", "front")
    result = text_model(handler).generate_structured(
        [TextMessage("system", "rules"), TextMessage("user", "context")], [photo], SCHEMA
    )

    assert result == {"features": []}
    assert captured["url"] == f"{BASE}/chat/completions"
    assert captured["auth"] == f"Bearer {KEY}"
    body = captured["body"]
    assert body["model"] == "configured-text-model"
    assert body["response_format"]["json_schema"]["schema"] == SCHEMA
    parts = body["messages"][-1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_chat_returns_the_reply_text() -> None:
    assert text_model(lambda _r: reply("Hello there")).chat([TextMessage("user", "hi")]) == (
        "Hello there"
    )


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(429, headers={"Retry-After": "12"}), AiRateLimitError),
        (httpx.Response(503), AiUnavailableError),
        (httpx.Response(400, text=CANARY), AiRequestRejectedError),
        (httpx.Response(200, text="not json at all"), AiBadOutputError),
        (httpx.Response(200, json=["a list"]), AiBadOutputError),
        (httpx.Response(200, json={"choices": []}), AiBadOutputError),
        (reply("   "), AiBadOutputError),
    ],
)
def test_vendor_failures_are_raised_as_typed_errors_never_swallowed(
    response: httpx.Response, error: type[Exception]
) -> None:
    with pytest.raises(error):
        text_model(lambda _r: response).chat([TextMessage("user", "hi")])


def test_a_rate_limit_carries_the_vendors_retry_hint() -> None:
    model = text_model(lambda _r: httpx.Response(429, headers={"Retry-After": "12"}))
    with pytest.raises(AiRateLimitError) as caught:
        model.chat([TextMessage("user", "hi")])
    assert caught.value.retry_after == 12.0

    odd = text_model(lambda _r: httpx.Response(429, headers={"Retry-After": "soon"}))
    with pytest.raises(AiRateLimitError) as caught_odd:
        odd.chat([TextMessage("user", "hi")])
    assert caught_odd.value.retry_after is None


def test_the_timeout_is_applied_and_a_timeout_is_typed() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["timeout"] = request.extensions["timeout"]
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(AiTimeoutError):
        text_model(handler).chat([TextMessage("user", "hi")])
    assert seen["timeout"]["read"] == 7.0


def test_an_unreachable_vendor_is_typed_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(AiUnavailableError):
        text_model(handler).chat([TextMessage("user", "hi")])


def test_structured_output_that_is_not_a_json_object_is_bad_output() -> None:
    with pytest.raises(AiBadOutputError):
        text_model(lambda _r: reply("[1, 2]")).generate_structured([], [], SCHEMA)
    with pytest.raises(AiBadOutputError):
        text_model(lambda _r: reply("not json")).generate_structured([], [], SCHEMA)


def test_errors_and_logs_never_carry_request_or_response_bodies(
    caplog: pytest.LogCaptureFixture,
) -> None:
    model = text_model(lambda _r: httpx.Response(400, text=CANARY))
    with caplog.at_level(logging.DEBUG), pytest.raises(AiRequestRejectedError) as caught:
        model.generate_structured([TextMessage("user", CANARY)], [], SCHEMA)
    assert CANARY not in str(caught.value)
    assert CANARY not in " ".join(record.getMessage() for record in caplog.records)


def test_image_edit_posts_the_photo_and_returns_the_decoded_image() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["is_multipart"] = request.headers["content-type"].startswith("multipart/form-data")
        captured["body"] = request.content
        return httpx.Response(
            200, json={"data": [{"b64_json": base64.b64encode(b"PNGDATA").decode()}]}
        )

    out = image_editor(handler).edit(
        ImageInput(b"src", "image/png", "front"), "make it older", "high"
    )

    assert out == b"PNGDATA"
    assert captured["url"] == f"{BASE}/images/edits"
    assert captured["is_multipart"]
    assert b"configured-image-model" in captured["body"]
    assert b"make it older" in captured["body"]


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(429), AiRateLimitError),
        (httpx.Response(500), AiUnavailableError),
        (httpx.Response(200, json={"data": []}), AiBadOutputError),
        (httpx.Response(200, json={"data": [{"b64_json": "%%%"}]}), AiBadOutputError),
        (httpx.Response(200, json={"data": [{"b64_json": ""}]}), AiBadOutputError),
    ],
)
def test_image_failures_are_typed(response: httpx.Response, error: type[Exception]) -> None:
    with pytest.raises(error):
        image_editor(lambda _r: response).edit(ImageInput(b"s", "image/png", "front"), "x", "high")
