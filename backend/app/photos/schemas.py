"""Response models for ``/photos/*`` (contract C1 PhotoSet; camelCase JSON).

Additive to C1 [Decided by delivery team]: ``acceptedCount`` on PhotoSet (the "2 of 3"
counter, AC5.2.6), ``captureMethod`` and ``updatedAt`` per photo, and the
``GET /photos/requirements`` document.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model: camelCase on the wire, snake_case in Python."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PhotoOut(CamelModel):
    """One required angle's current photo."""

    angle: str
    status: Literal["missing", "accepted", "rejected"]
    #: Reason codes of the latest rejection (only for ``rejected``).
    reasons: list[str] = Field(default_factory=list)
    #: ``/media/{fileId}`` for an accepted photo; read it with the access token.
    image_url: str | None = None
    capture_method: Literal["upload", "camera"] | None = None
    updated_at: datetime | None = None


class IdentityOut(CamelModel):
    """The freshly computed same-person result ([IV] §1)."""

    status: Literal["incomplete", "consistent", "mismatch"]
    mismatched_angles: list[str]


class PhotoSet(CamelModel):
    """``GET /photos`` and ``PUT /photos/{angle}`` response."""

    required_angles: list[str]
    accepted_count: int
    photos: list[PhotoOut]
    identity: IdentityOut


class PhotoRuleOut(CamelModel):
    """A requirement rule (the browser pairs it with its example illustration)."""

    id: str
    text: str


class AngleOut(CamelModel):
    """A required angle and how to take it."""

    id: str
    label: str
    instruction: str
    turn_hint: str
    illustration: Literal["front", "left", "right"]


class PhotoRequirements(CamelModel):
    """``GET /photos/requirements`` response (FR-005; [PC] §2-§3)."""

    catalog_version: str
    rules: list[PhotoRuleOut]
    guidance: list[str]
    angles: list[AngleOut]
    max_upload_bytes: int
    accepted_types: list[str]
