"""Chat fixtures: the report fixtures plus a recording text FAKE wired into the chat service.

Nothing here calls OpenAI; the daily-limit tests move the frozen clock instead of waiting.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.fakes import FakeTextModel
from tests.factories import SignedInUser
from tests.identity.conftest import bearer
from tests.report.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    Harness,
    app,
    client,
    consistent,
    email_fake,
    fake_gateway,
    harness,
    insert_payment,
    make_paid_user,
    media_root,
    paid,
    run_to_done,
    seed_definition,
    settings_overrides,
    submitted,
    text_model,
    upload_consistent_set,
    webhooks,
)


@pytest.fixture
def chat_model(app: FastAPI) -> FakeTextModel:  # noqa: F811
    """The recording fake behind the chat service (the report-writing fake is separate)."""
    model = FakeTextModel()
    app.state.chat.text_model = model
    return model


def send(client: TestClient, user: SignedInUser, text: str) -> Any:  # noqa: F811
    """``POST /chat/messages``."""
    return client.post("/chat/messages", json={"text": text}, headers=bearer(user.access_token))


def history(client: TestClient, user: SignedInUser) -> Any:  # noqa: F811
    """``GET /chat/messages``."""
    return client.get("/chat/messages", headers=bearer(user.access_token))
