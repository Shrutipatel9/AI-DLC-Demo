"""Report fixtures: the image harness (a full pipeline with the recording image fake) plus
small helpers. Nothing here calls OpenAI, Stripe or a mail provider."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.analysis.conftest import harness  # noqa: F401  (pytest fixture re-used here)
from tests.factories import SignedInUser
from tests.identity.conftest import bearer
from tests.images.conftest import (  # noqa: F401  (pytest fixtures re-used here)
    Harness,
    ImageHarness,
    app,
    client,
    consistent,
    email_fake,
    fake_gateway,
    image_harness,
    insert_payment,
    make_paid_user,
    media_root,
    paid,
    seed_definition,
    settings_overrides,
    submitted,
    text_model,
    upload_consistent_set,
    webhooks,
)


def get_report(client: TestClient, user: SignedInUser) -> Any:  # noqa: F811
    """``GET /report``."""
    return client.get("/report", headers=bearer(user.access_token))


def get_home(client: TestClient, user: SignedInUser) -> Any:  # noqa: F811
    """``GET /home``."""
    return client.get("/home", headers=bearer(user.access_token))


def get_pdf(client: TestClient, user: SignedInUser) -> Any:  # noqa: F811
    """``GET /report/pdf``."""
    return client.get("/report/pdf", headers=bearer(user.access_token))


def run_to_done(client: TestClient, user: SignedInUser, harness: Harness) -> None:  # noqa: F811
    """Start the analysis and let the in-process worker finish it."""
    assert client.post("/analysis/runs", headers=bearer(user.access_token)).status_code == 202
    harness.drain()
