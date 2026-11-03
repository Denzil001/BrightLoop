"""Persist actual scheduler observations, independent of API process uptime."""
from datetime import datetime
import uuid
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class SchedulerState(Base):
    __tablename__ = "scheduler_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("billing_runs.id", ondelete="RESTRICT"))
    continue_after_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_scheduler_singleton"),
        CheckConstraint("state IN ('RUNNING', 'IDLE', 'FAILED', 'STOPPED')", name="ck_scheduler_state"),
        CheckConstraint("interval_seconds BETWEEN 10 AND 86400", name="ck_scheduler_interval"),
    )
