"""Chat request and response bodies (contract C1: ``ChatState``, ``ChatReply``)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

MAX_MESSAGE_LENGTH = 2000


class _Out(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChatMessageOut(_Out):
    """One stored message."""

    role: Literal["user", "assistant"]
    text: str
    created_at: datetime


class ChatStateOut(_Out):
    """The conversation and today's remaining messages."""

    messages: list[ChatMessageOut]
    remaining_today: int = Field(ge=0)
    resets_at: datetime


class ChatReplyOut(_Out):
    """The assistant's whole reply."""

    reply: str
    remaining_today: int = Field(ge=0)
    resets_at: datetime


class ChatSendIn(BaseModel):
    """A message to send."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
