"""Media HTTP route (contract C1 ``GET /media/{fileId}``; AC1.10.2, AC5.2.7).

Protected (mounted with ``current_user``) and owner-checked: another user's file, or a file
that does not exist, is 404. Responses are ``no-store`` so no browser or proxy keeps a copy
of a face photo.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from sqlalchemy.orm import Session

from app.identity.public import AuthenticatedUser, current_user
from app.media.dependencies import get_media_store
from app.media.services import MediaStore
from app.platform.db import get_session
from app.platform.errors import error_responses

router = APIRouter(tags=["media"])

SessionDep = Annotated[Session, Depends(get_session)]
MediaDep = Annotated[MediaStore, Depends(get_media_store)]
UserDep = Annotated[AuthenticatedUser, Depends(current_user)]


@router.get(
    "/media/{fileId}",
    response_class=Response,
    responses={
        200: {
            "description": "File bytes",
            "content": {"image/jpeg": {}, "image/png": {}},
        },
        **error_responses(401, 404),
    },
    summary="Owner-checked private file (photo); never public",
)
def get_media(
    file_id: Annotated[uuid.UUID, Path(alias="fileId")],
    user: UserDep,
    session: SessionDep,
    media: MediaDep,
) -> Response:
    """Return the file's bytes to its owner; 404 for anyone else (AC1.10.2)."""
    stored = media.get(session, file_id, user.user_id)
    return Response(
        content=stored.data,
        media_type=stored.content_type,
        headers={"Cache-Control": "no-store", "Content-Disposition": "inline"},
    )
