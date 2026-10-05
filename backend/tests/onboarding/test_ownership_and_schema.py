"""Auth, ownership, configuration, definition immutability and the 0003 migration round-trip
(BR6.2, NFR2.8; plan decisions D1, D2; AC1.2.2)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.onboarding.definition import DefinitionError, QuestionnaireDefinition
from app.onboarding.models import QuestionnaireDefinitionRecord, QuestionnaireResponse
from app.onboarding.repositories import ensure_definition_stored
from app.onboarding.services import OnboardingService
from app.platform.db import Base
from app.platform.email.fake import RecordingEmailSender
from app.platform.settings import Settings
from tests.conftest import alembic_config
from tests.factories import SignedInUser, verified_user
from tests.helpers import make_settings
from tests.onboarding.conftest import bearer, give_consent, put_answer

ONBOARDING_ROUTES = [
    ("GET", "/onboarding/consent"),
    ("POST", "/onboarding/consent"),
    ("GET", "/onboarding/questionnaire"),
    ("GET", "/onboarding/response"),
    ("PUT", "/onboarding/response/answers/q1"),
    ("POST", "/onboarding/response/submit"),
]
U3_TABLES = {"consent_records", "questionnaire_definitions", "questionnaire_responses"}


@pytest.mark.parametrize(("method", "path"), ONBOARDING_ROUTES)
def test_every_onboarding_route_needs_a_valid_token(
    client: TestClient, method: str, path: str
) -> None:
    for headers in ({}, bearer("not-a-token")):
        response = client.request(method, path, json={}, headers=headers)
        assert response.status_code == 401, (method, path)
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"


def test_users_only_ever_see_their_own_consent_and_answers(
    client: TestClient, email_fake: RecordingEmailSender, consented: SignedInUser
) -> None:
    put_answer(client, consented, "q1", "Secret occupation")
    other = verified_user(client, email_fake)
    assert (
        client.get("/onboarding/consent", headers=bearer(other.access_token)).json()["given"]
        is False
    )
    give_consent(client, other)
    theirs = client.get("/onboarding/response", headers=bearer(other.access_token)).json()
    assert theirs["answers"] == {}
    put_answer(client, other, "q1", "Other")
    mine = client.get("/onboarding/response", headers=bearer(consented.access_token)).json()
    assert mine["answers"]["q1"]["value"] == "Secret occupation"


def test_onboarding_settings_validate_the_support_url_and_empty_paths() -> None:
    settings = make_settings(ONBOARDING_CONSENT_FILE="", ONBOARDING_SUPPORT_URL="")
    assert settings.onboarding_consent_file is None
    assert settings.onboarding_support_url is None
    url = "https://support.example.test/help"
    assert make_settings(ONBOARDING_SUPPORT_URL=f" {url} ").onboarding_support_url == url
    with pytest.raises(ValueError, match="ONBOARDING_SUPPORT_URL"):
        make_settings(ONBOARDING_SUPPORT_URL="http://insecure.example.test")
    assert isinstance(settings, Settings)


@pytest.mark.parametrize(
    "settings_overrides", [{"ONBOARDING_SUPPORT_URL": "https://support.example.test/help"}]
)
def test_the_configured_support_link_is_sent_with_the_definition(
    client: TestClient, consented: SignedInUser
) -> None:
    body = client.get("/onboarding/questionnaire", headers=bearer(consented.access_token)).json()
    assert body["supportUrl"] == "https://support.example.test/help"


def test_a_stored_version_cannot_change_silently(
    db_session: Session, seed_definition: QuestionnaireDefinition
) -> None:
    now = datetime(2026, 10, 1, tzinfo=UTC)
    ensure_definition_stored(db_session, seed_definition, now)
    ensure_definition_stored(db_session, seed_definition, now)  # idempotent
    changed = seed_definition.model_copy(update={"disclaimer_text": "Different."})
    with pytest.raises(DefinitionError, match="new version"):
        ensure_definition_stored(db_session, changed, now)


def test_a_new_definition_version_keeps_only_answers_it_still_asks_for(
    client: TestClient,
    consented: SignedInUser,
    onboarding: OnboardingService,
    db_session: Session,
) -> None:
    put_answer(client, consented, "q1", "Designer")
    user_id = uuid.UUID(consented.user_id)
    row = db_session.query(QuestionnaireResponse).filter_by(user_id=user_id).one()
    db_session.add(
        QuestionnaireDefinitionRecord(
            version="qs-v0", definition={"old": True}, created_at=datetime.now(UTC)
        )
    )
    db_session.flush()
    row.definition_version = "qs-v0"
    row.answers = {**row.answers, "q_retired": {"value": "x", "medical": False}}
    db_session.commit()
    body = put_answer(client, consented, "q2", "never").json()
    assert set(body["answers"]) == {"q1", "q2"}
    db_session.refresh(row)
    assert row.definition_version == "qs-v1"
    assert onboarding.definition.version == "qs-v1"


@pytest.fixture
def scratch_database(database_url: str) -> Iterator[str]:
    """A throwaway empty database, dropped afterwards."""
    name = f"app_u3_migrations_{uuid.uuid4().hex[:8]}_test"
    parsed = make_url(database_url)
    admin = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield parsed.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def test_migration_0003_round_trip_and_matches_the_models(scratch_database: str) -> None:
    cfg = alembic_config(scratch_database)
    engine = create_engine(scratch_database)
    try:
        command.upgrade(cfg, "head")
        assert set(inspect(engine).get_table_names()) >= U3_TABLES
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        onboarding_diff = [d for d in diff if any(t in repr(d) for t in U3_TABLES)]
        assert onboarding_diff == []
        command.downgrade(cfg, "0002_u2_session_security")
        tables = set(inspect(engine).get_table_names())
        assert not (U3_TABLES & tables)
        assert "users" in tables
        command.upgrade(cfg, "head")
        assert set(inspect(engine).get_table_names()) >= U3_TABLES
    finally:
        engine.dispose()
