"""Chat HTTP routes (contract C1 ``/chat/messages``).

Protected, paywalled (402), report required (404), always ``Cache-Control: no-store``. A user
only ever reads and writes their own conversation. Handlers stay thin.
"""

from __future__ import annotations

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.chat.schemas import ChatMessageOut, ChatReplyOut, ChatSendIn, ChatStateOut
from app.chat.service import ChatService
from app.identity.public import AuthenticatedUser, current_user
from app.platform.db import get_session
from app.platform.errors import error_responses

SessionDep = Annotated[Session, Depends(get_session)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]


def get_chat_service(request: Request) -> ChatService:
    """The chat service wired by the app factory."""
    service: ChatService = request.app.state.chat
    return service


def no_store(response: Response) -> None:
    """A conversation is personal: never let a browser or proxy cache it."""
    response.headers["Cache-Control"] = "no-store"


ChatDep = Annotated[ChatService, Depends(get_chat_service)]

router = APIRouter(tags=["chat"], dependencies=[Depends(no_store)])


@router.get(
    "/chat/messages",
    response_model=ChatStateOut,
    response_model_by_alias=True,
    responses=error_responses(401, 402, 404),
    summary="Conversation history and today's remaining messages",
)
def get_chat(user: UserDep, session: SessionDep, service: ChatDep) -> ChatStateOut:
    """402 without payment; 404 ``REPORT_NOT_READY`` while there is no report."""
    state = service.state(session, user.user_id)
    return ChatStateOut(
        messages=[
            ChatMessageOut(
                role=cast(Literal["user", "assistant"], m.role),
                text=m.text,
                created_at=m.created_at,
            )
            for m in state.messages
        ],
        remaining_today=state.remaining_today,
        resets_at=state.resets_at,
    )


@router.post(
    "/chat/messages",
    response_model=ChatReplyOut,
    response_model_by_alias=True,
    responses=error_responses(401, 402, 404, 422, 429, 502, 504),
    summary="Send a message; returns the whole reply",
)
def post_message(
    body: ChatSendIn, user: UserDep, session: SessionDep, service: ChatDep
) -> ChatReplyOut:
    """429 ``CHAT_DAILY_LIMIT_REACHED`` (no AI call); 502/504 when the model fails (not counted)."""
    reply = service.send(session, user.user_id, body.text)
    return ChatReplyOut(
        reply=reply.reply, remaining_today=reply.remaining_today, resets_at=reply.resets_at
    )
