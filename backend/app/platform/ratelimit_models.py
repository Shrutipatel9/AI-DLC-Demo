"""Table for the PostgreSQL-backed sliding-window rate limiter (NFR2.9, NFR11.2)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.db import Base


class RateLimitHit(Base):
    """One recorded request for a limiter key (for example ``/auth/login:203.0.113.7``)."""

    __tablename__ = "rate_limit_hits"
    __table_args__ = (Index("ix_rate_limit_hits_key_hit_at", "key", "hit_at"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    key: Mapped[str] = mapped_column(String(200))
    hit_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
