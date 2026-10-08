"""Chat use cases (US10.1-US10.3).

Order of a send: paywall (402) and report (404) -> reserve one of today's messages (429 with the
reset time, before any AI call) -> store the user's message -> ask the model -> store the reply.
A failed AI call gives the reservation back, so only successful replies count (AC10.3.2), and
the user's message stays stored (AC10.1.4).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.ai.public import AiError, AiTimeoutError, TextModel
from app.analysis.public import latest_result_view
from app.chat import repositories
from app.chat.grounding import build_context, build_messages
from app.onboarding.public import OnboardingService, get_non_medical_answers
from app.payments.public import PaymentService, require_paid
from app.platform.clock import Clock
from app.platform.errors import (
    ChatDailyLimitReached,
    ReportNotReady,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from app.report_writing.public import AnswerForAi

logger = logging.getLogger("chat")


@dataclass(frozen=True)
class StoredMessage:
    """A message as the API shows it."""

    role: str
    text: str
    created_at: datetime


@dataclass(frozen=True)
class ChatState:
    """The conversation plus today's allowance."""

    messages: list[StoredMessage]
    remaining_today: int
    resets_at: datetime


@dataclass(frozen=True)
class ChatReply:
    """The reply plus today's allowance."""

    reply: str
    remaining_today: int
    resets_at: datetime


class ChatService:
    """The Beauty Assistant.

    Args:
        text_model: The text port (the fake in tests; ``chat`` is the only call used).
        payments: The paywall.
        onboarding: Source of the non-medical answers.
        clock: Time source (the daily window is the UTC day).
        daily_limit: Counted replies allowed per user per UTC day.
        history_messages: How many latest stored messages are sent to the model.
    """

    def __init__(
        self,
        *,
        text_model: TextModel,
        payments: PaymentService,
        onboarding: OnboardingService,
        clock: Clock,
        daily_limit: int,
        history_messages: int,
    ) -> None:
        self.text_model = text_model
        self.payments = payments
        self.onboarding = onboarding
        self.clock = clock
        self.daily_limit = daily_limit
        self.history_messages = history_messages

    def _resets_at(self) -> datetime:
        now = self.clock.now()
        return datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=now.tzinfo)

    def _result(self, session: Session, user_id: uuid.UUID) -> dict[str, Any]:
        require_paid(self.payments, session, user_id)
        view = latest_result_view(session, user_id)
        if view is None or view.user_id != user_id:
            raise ReportNotReady()
        return dict(view.result)

    def state(self, session: Session, user_id: uuid.UUID) -> ChatState:
        """History and remaining messages (402 unpaid, 404 without a report)."""
        self._result(session, user_id)
        used = repositories.used_today(session, user_id, self.clock.now().date())
        rows = repositories.all_messages(session, user_id)
        return ChatState(
            messages=[StoredMessage(row.role, row.text, row.created_at) for row in rows],
            remaining_today=max(0, self.daily_limit - used),
            resets_at=self._resets_at(),
        )

    def send(self, session: Session, user_id: uuid.UUID, text: str) -> ChatReply:
        """Answer one message.

        Raises:
            ChatDailyLimitReached: 429, no AI call was made.
            UpstreamTimeout: 504, the model did not answer in time (not counted).
            UpstreamUnavailable: 502, the model failed (not counted).
        """
        result = self._result(session, user_id)
        now = self.clock.now()
        day = now.date()
        if not repositories.reserve(session, user_id, day, self.daily_limit):
            session.rollback()
            resets_at = self._resets_at()
            raise ChatDailyLimitReached(
                details=[{"resetsAt": resets_at.isoformat()}],
                retry_after=int((resets_at - now).total_seconds()),
            )
        repositories.add_message(session, user_id=user_id, role="user", text=text, now=now)
        session.commit()  # the message and the reservation are durable before the slow call

        answers = [
            AnswerForAi(item.question_text, item.answer_text)
            for item in get_non_medical_answers(self.onboarding, session, user_id)
        ]
        history = [
            (row.role, row.text)
            for row in repositories.recent_messages(session, user_id, self.history_messages)
        ]
        messages = build_messages(build_context(result, answers), history)
        try:
            reply = self.text_model.chat(messages)
        except AiError as error:
            repositories.release(session, user_id, day)
            session.commit()
            logger.warning("chat reply failed", extra={"event": "chat.failed"})
            if isinstance(error, AiTimeoutError):
                raise UpstreamTimeout(
                    "The assistant took too long to answer. Please try again."
                ) from None
            raise UpstreamUnavailable("The assistant couldn't answer. Please try again.") from None

        repositories.add_message(
            session, user_id=user_id, role="assistant", text=reply, now=self.clock.now()
        )
        used = repositories.used_today(session, user_id, day)
        session.commit()
        return ChatReply(
            reply=reply,
            remaining_today=max(0, self.daily_limit - used),
            resets_at=self._resets_at(),
        )
