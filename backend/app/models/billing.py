import uuid
from datetime import date, datetime
from typing import Optional
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class BillingRun(Base):
    __tablename__ = "billing_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    retry_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("billing_runs.id", ondelete="RESTRICT", name="fk_billing_runs_retry_of"), nullable=True
    )
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    summary_counts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("trigger IN ('MANUAL', 'CLI', 'SCHEDULED')", name="ck_billing_runs_trigger"),
        CheckConstraint(
            "state IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'INTERRUPTED')",
            name="ck_billing_runs_state",
        ),
    )

    requester = relationship("User")
    outcomes = relationship("BillingOutcome", back_populates="run", cascade="all, delete-orphan")


class BillingOutcome(Base):
    __tablename__ = "billing_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("billing_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    safe_error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("state IN ('CREATED', 'EXISTING', 'FAILED')", name="ck_billing_outcomes_state"),
    )

    run = relationship("BillingRun", back_populates="outcomes", foreign_keys=[run_id])
    subscription = relationship("Subscription", foreign_keys=[subscription_id])
    invoice = relationship("Invoice", foreign_keys=[invoice_id])


class EmailAttempt(Base):
    __tablename__ = "email_attempts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    auth_challenge_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth_challenges.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    safe_error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('INVOICE_SEND', 'PASSWORD_RESET', 'SIGNUP_VERIFICATION')",
            name="ck_email_attempts_kind",
        ),
        CheckConstraint("status IN ('PENDING', 'SENT', 'FAILED', 'UNKNOWN')", name="ck_email_attempts_status"),
        CheckConstraint("attempt_count >= 1", name="ck_email_attempts_count_pos"),
    )

    invoice = relationship("Invoice", back_populates="email_attempts", foreign_keys=[invoice_id])
    auth_challenge = relationship("AuthChallenge", foreign_keys=[auth_challenge_id])
