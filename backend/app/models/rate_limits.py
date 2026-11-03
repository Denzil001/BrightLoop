"""Shared bounded sliding-window authentication attempt state."""
from datetime import datetime
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class RateLimitWindow(Base):
    __tablename__ = "rate_limit_windows"
    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[list] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
