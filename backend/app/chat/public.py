"""The Chat module's public interface. Other modules import only this.

- ``build_chat``: the BeautyAssistant service from settings, its text model and collaborators.
- ``router``: ``/chat/messages`` (mounted as a protected route).
"""

from __future__ import annotations

from app.ai.public import TextModel
from app.chat.grounding import MEDICAL_DECLINE_INSTRUCTION
from app.chat.routes import router
from app.chat.service import ChatService
from app.onboarding.public import OnboardingService
from app.payments.public import PaymentService
from app.platform.clock import Clock
from app.platform.settings import Settings

__all__ = ["MEDICAL_DECLINE_INSTRUCTION", "ChatService", "build_chat", "router"]


def build_chat(
    settings: Settings,
    *,
    text_model: TextModel,
    payments: PaymentService,
    onboarding: OnboardingService,
    clock: Clock,
) -> ChatService:
    """Create the chat service."""
    return ChatService(
        text_model=text_model,
        payments=payments,
        onboarding=onboarding,
        clock=clock,
        daily_limit=settings.chat_daily_limit,
        history_messages=settings.chat_history_messages,
    )
