"""The chat API through the real app, worker and pipeline (US10.1, US10.2, US10.3).

The text vendor is the recording FAKE: tests read exactly what the model would have been sent.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.errors import AiTimeoutError
from app.ai.fakes import FakeTextModel
from app.chat.grounding import MEDICAL_DECLINE_INSTRUCTION
from app.chat.models import ChatMessage
from app.chat.public import build_chat
from app.platform.clock import FrozenClock
from tests.chat.conftest import history, send
from tests.factories import SignedInUser
from tests.report.conftest import Harness, get_report, run_to_done


def _sent(model: FakeTextModel, index: int = -1) -> str:
    return " ".join(message.content for message in model.calls[index].messages)


# --- US10.1: ask about my report -------------------------------------------------------------


def test_the_grounding_has_my_symmetry_score_and_no_medical_answer(
    client: TestClient,
    make_paid_user: Callable[..., SignedInUser],
    harness: Harness,
    chat_model: FakeTextModel,
    seed_definition: Any,
) -> None:
    """AC10.1.1, AC10.2.1: stored values reach the model; medical answers never do."""
    user = make_paid_user(
        {
            "q14": ("CANARY-LIKED-FEATURE-eyes", None),
            "q9": (True, "CANARY-MEDICATION-FOLLOWUP-aspirin"),
            "q11": (True, "CANARY-ALLERGY-FOLLOWUP-latex"),
        }
    )
    run_to_done(client, user, harness)
    score = get_report(client, user).json()["assessments"]["symmetry"]["score"]

    response = send(client, user, "What does my symmetry score mean?")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["reply"] == "This is a fake assistant reply."
    assert body["remainingToday"] == 49
    sent = _sent(chat_model)
    assert f'"score": {score}' in sent
    assert "What does my symmetry score mean?" in sent
    assert "CANARY-LIKED-FEATURE-eyes" in sent  # a non-medical answer is allowed
    for medical in ("q8", "q9", "q10", "q11", "q12"):
        assert seed_definition.question(medical).text not in sent
    assert "CANARY-MEDICATION" not in sent
    assert "CANARY-ALLERGY" not in sent
    system = [m.content for m in chat_model.calls[-1].messages if m.role == "system"]
    assert MEDICAL_DECLINE_INSTRUCTION in system[0]


def test_my_conversation_is_there_when_i_return_and_never_visible_to_others(
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    chat_model: FakeTextModel,
    make_paid_user: Callable[..., SignedInUser],
) -> None:
    """AC10.1.2: history is kept in order; another user has no report, so gets 404."""
    run_to_done(client, paid, harness)
    assert send(client, paid, "First question").status_code == 200
    assert send(client, paid, "Second question").status_code == 200

    state = history(client, paid).json()

    assert [(m["role"], m["text"]) for m in state["messages"]] == [
        ("user", "First question"),
        ("assistant", "This is a fake assistant reply."),
        ("user", "Second question"),
        ("assistant", "This is a fake assistant reply."),
    ]
    assert state["remainingToday"] == 48
    assert state["resetsAt"].startswith("2026-10-02T00:00:00")
    other = make_paid_user()
    assert history(client, other).status_code == 404
    assert history(client, other).json()["error"]["code"] == "REPORT_NOT_READY"
    assert send(client, other, "hello").status_code == 404


def test_a_failed_ai_call_keeps_my_message_and_does_not_count(
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    chat_model: FakeTextModel,
) -> None:
    """AC10.1.4, AC10.3.2: 502, the message is stored, the allowance is untouched."""
    run_to_done(client, paid, harness)
    chat_model.fail_next()

    failed = send(client, paid, "Will this fail?")

    assert failed.status_code == 502
    assert failed.json()["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    state = history(client, paid).json()
    assert [(m["role"], m["text"]) for m in state["messages"]] == [("user", "Will this fail?")]
    assert state["remainingToday"] == 50


def test_a_slow_ai_call_is_a_504_that_does_not_count(
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    chat_model: FakeTextModel,
) -> None:
    run_to_done(client, paid, harness)
    chat_model.fail_next(AiTimeoutError("slow"))

    response = send(client, paid, "Are you there?")

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"
    assert history(client, paid).json()["remainingToday"] == 50


def test_an_unpaid_user_gets_402_and_no_ai_call(
    client: TestClient, consistent: SignedInUser, chat_model: FakeTextModel
) -> None:
    """US10.1: the paywall is enforced on the server."""
    assert history(client, consistent).status_code == 402
    assert send(client, consistent, "hi").json()["error"]["code"] == "PAYMENT_REQUIRED"
    assert chat_model.calls == []


def test_a_paid_user_without_a_report_gets_404_and_bad_input_is_422(
    client: TestClient, paid: SignedInUser, chat_model: FakeTextModel
) -> None:
    """US10.1: no report 404, no token 401, empty or oversized text 422."""
    assert history(client, paid).status_code == 404
    assert client.get("/chat/messages").status_code == 401
    assert send(client, paid, "").status_code == 422
    assert send(client, paid, "x" * 2001).status_code == 422
    assert chat_model.calls == []


def test_only_the_latest_messages_are_sent_to_the_model(
    app: FastAPI,
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    chat_model: FakeTextModel,
) -> None:
    run_to_done(client, paid, harness)
    app.state.chat.history_messages = 3
    for text in ("one", "two", "three"):
        assert send(client, paid, text).status_code == 200

    sent = [(m.role, m.content) for m in chat_model.calls[-1].messages if m.role != "system"]

    assert (
        sent
        == [
            ("assistant", "This is a fake assistant reply."),
            ("user", "two"),
            ("assistant", "This is a fake assistant reply."),
            ("user", "three"),
        ][-3:]
    )


# --- US10.3: the daily limit -----------------------------------------------------------------


def test_over_the_limit_is_refused_with_the_reset_time_and_no_ai_call(
    app: FastAPI,
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    chat_model: FakeTextModel,
    frozen_clock: FrozenClock,
) -> None:
    """AC10.3.1: the limit counts replies; the refusal names 00:00 UTC; tomorrow it resets."""
    run_to_done(client, paid, harness)
    app.state.chat.daily_limit = 2
    assert send(client, paid, "a").status_code == 200
    assert send(client, paid, "b").status_code == 200
    calls = len(chat_model.calls)

    refused = send(client, paid, "c")

    assert refused.status_code == 429
    error = refused.json()["error"]
    assert error["code"] == "CHAT_DAILY_LIMIT_REACHED"
    assert error["details"][0]["resetsAt"].startswith("2026-10-02T00:00:00")
    assert refused.headers["retry-after"] == str(14 * 3600)
    assert len(chat_model.calls) == calls
    assert history(client, paid).json()["remainingToday"] == 0
    stored = [m["text"] for m in history(client, paid).json()["messages"]]
    assert "c" not in stored  # a refused message is not stored

    # The chat service's own clock moves past 00:00 UTC (the access token keeps its own).
    app.state.chat.clock = FrozenClock(frozen_clock.now() + timedelta(hours=14, minutes=1))
    assert send(client, paid, "c").status_code == 200


def test_a_failed_call_frees_its_slot_for_the_next_message(
    app: FastAPI,
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    chat_model: FakeTextModel,
) -> None:
    """AC10.3.2 at the limit: only successful replies count."""
    run_to_done(client, paid, harness)
    app.state.chat.daily_limit = 1
    chat_model.fail_next()
    assert send(client, paid, "a").status_code == 502

    assert send(client, paid, "a again").status_code == 200
    assert send(client, paid, "b").status_code == 429


def test_the_limit_comes_from_configuration(app: FastAPI) -> None:
    """AC10.3.4: the default is 50 and a changed setting applies with no code change."""
    settings = app.state.settings
    assert app.state.chat.daily_limit == settings.chat_daily_limit == 50
    changed = settings.model_copy(update={"chat_daily_limit": 7, "chat_history_messages": 4})
    service = build_chat(
        changed,
        text_model=FakeTextModel(),
        payments=app.state.payments,
        onboarding=app.state.onboarding,
        clock=app.state.clock,
    )
    assert (service.daily_limit, service.history_messages) == (7, 4)


def test_the_user_message_row_is_stored_before_the_reply(
    client: TestClient,
    paid: SignedInUser,
    harness: Harness,
    chat_model: FakeTextModel,
    db_session: Session,
) -> None:
    run_to_done(client, paid, harness)
    assert send(client, paid, "stored?").status_code == 200

    rows = db_session.scalars(
        select(ChatMessage).where(ChatMessage.user_id == paid.user_id).order_by(ChatMessage.id)
    ).all()

    assert [row.role for row in rows] == ["user", "assistant"]
