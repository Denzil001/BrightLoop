import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Boolean,
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    creator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    seat_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    next_billing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "state IN ('DRAFT', 'QUOTATION', 'CONFIRMED', 'ACTIVE', 'PAUSED', 'CLOSED')",
            name="ck_subscriptions_state",
        ),
        CheckConstraint("seat_quantity > 0", name="ck_subscriptions_seat_qty_pos"),
        # Target for composite foreign key in invoices(subscription_id, customer_id)
        UniqueConstraint("id", "customer_id", name="uq_subscriptions_id_customer"),
    )

    customer = relationship("Customer", back_populates="subscriptions", foreign_keys=[customer_id])
    plan = relationship("Plan", back_populates="subscriptions", foreign_keys=[plan_id])
    creator = relationship("User", foreign_keys=[creator_id])
    terms = relationship("SubscriptionTerm", back_populates="subscription", cascade="all, delete-orphan", foreign_keys="[SubscriptionTerm.subscription_id]")
    agreement_versions = relationship("AgreementVersion", back_populates="subscription", cascade="all, delete-orphan", foreign_keys="[AgreementVersion.subscription_id]")
    requests = relationship("SubscriptionRequest", back_populates="subscription", cascade="all, delete-orphan", foreign_keys="[SubscriptionRequest.subscription_id]")
    events = relationship("SubscriptionEvent", back_populates="subscription", cascade="all, delete-orphan", foreign_keys="[SubscriptionEvent.subscription_id]")
    invoices = relationship("Invoice", back_populates="subscription", foreign_keys="[Invoice.subscription_id]")


class SubscriptionTerm(Base):
    __tablename__ = "subscription_terms"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    original_anchor_date: Mapped[date] = mapped_column(Date, nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    allow_pause: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_resume: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_renewal: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_early_closure: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_close_on_expiry: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    source_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("subscription_id", "sequence", name="uq_subscription_terms_seq"),
        # Target for composite foreign key in invoices(term_id, subscription_id)
        UniqueConstraint("id", "subscription_id", name="uq_subscription_terms_id_sub"),
        CheckConstraint("expiry_date > start_date", name="ck_sub_terms_expiry_gt_start"),
        CheckConstraint("interval IN ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY')", name="ck_sub_terms_interval"),
        ForeignKeyConstraint(
            ["source_version_id", "subscription_id"],
            ["agreement_versions.id", "agreement_versions.subscription_id"],
            ondelete="RESTRICT",
            name="fk_subscription_terms_source_version_sub",
            # Agreement versions also reference their term. Order this existing
            # constraint after table creation so schema comparison sees both FKs.
            use_alter=True,
        ),
    )

    subscription = relationship("Subscription", back_populates="terms", foreign_keys=[subscription_id])
    source_version = relationship("AgreementVersion", foreign_keys=[source_version_id], post_update=True)
    pauses = relationship("SubscriptionPause", back_populates="term", cascade="all, delete-orphan", foreign_keys="[SubscriptionPause.term_id]")


class AgreementVersion(Base, TimestampMixin):
    __tablename__ = "agreement_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    term_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_terms.id", ondelete="RESTRICT"),
        nullable=True,
    )
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("quotation_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_number: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    issued_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_until: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    seat_quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    proposed_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    proposed_expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    proposed_interval: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    payment_term_days: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), default="INR", nullable=False)
    policy_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    pricing_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    validity_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    __table_args__ = (
        UniqueConstraint("subscription_id", "sequence", name="uq_agreement_versions_seq"),
        # Target for composite foreign key in invoices(agreement_id, subscription_id)
        UniqueConstraint("id", "subscription_id", name="uq_agreement_versions_id_sub"),
        CheckConstraint("state IN ('DRAFT', 'ISSUED', 'ACCEPTED', 'SUPERSEDED')", name="ck_agreement_versions_state"),
        CheckConstraint("seat_quantity > 0", name="ck_agreement_versions_seat_qty_pos"),
        CheckConstraint("payment_term_days >= 0", name="ck_agreement_versions_payment_terms_nonneg"),
        CheckConstraint("validity_days >= 0", name="ck_agreement_versions_validity_nonneg"),
        Index(
            "uq_agreement_versions_one_draft",
            "subscription_id",
            unique=True,
            postgresql_where=text("state = 'DRAFT'"),
        ),
        Index(
            "uq_agreement_versions_accepted_effective",
            "subscription_id",
            "effective_from",
            unique=True,
            postgresql_where=text("state = 'ACCEPTED'"),
        ),
    )

    subscription = relationship("Subscription", back_populates="agreement_versions", foreign_keys=[subscription_id])
    term = relationship("SubscriptionTerm", foreign_keys=[term_id], post_update=True)
    lines = relationship("AgreementLine", back_populates="version", cascade="all, delete-orphan")
    discounts = relationship("AgreementDiscount", back_populates="version", cascade="all, delete-orphan")


class AgreementLine(Base):
    __tablename__ = "agreement_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agreement_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=True,
    )
    variant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="RESTRICT"),
        nullable=True,
    )
    snapshot_name: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    snapshot_variant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("version_id", "ordinal", name="uq_agreement_lines_ordinal"),
        UniqueConstraint("id", "version_id", name="uq_agreement_lines_id_version"),
        CheckConstraint("kind IN ('PLAN_FEE', 'EXCESS_SEATS', 'INCLUDED', 'ADDON')", name="ck_agreement_lines_kind"),
        CheckConstraint("quantity > 0", name="ck_agreement_lines_quantity_pos"),
        CheckConstraint("unit_price >= 0", name="ck_agreement_lines_unit_price_nonneg"),
        ForeignKeyConstraint(
            ["variant_id", "product_id"],
            ["product_variants.id", "product_variants.product_id"],
            ondelete="RESTRICT",
            name="fk_agreement_lines_variant_product",
        ),
    )

    version = relationship("AgreementVersion", back_populates="lines")
    product = relationship("Product", foreign_keys=[product_id])
    variant = relationship("ProductVariant", foreign_keys=[variant_id])
    taxes = relationship("AgreementLineTax", back_populates="line", cascade="all, delete-orphan")


class AgreementLineTax(Base):
    __tablename__ = "agreement_line_taxes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agreement_lines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_tax_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tax_rules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    snapshot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_classification: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)

    __table_args__ = (
        UniqueConstraint("line_id", "source_tax_id", name="uq_agreement_line_taxes"),
        CheckConstraint("snapshot_rate >= 0 AND snapshot_rate <= 100", name="ck_agreement_line_tax_rate"),
    )

    line = relationship("AgreementLine", back_populates="taxes")
    source_tax = relationship("TaxRule")


class AgreementDiscount(Base):
    __tablename__ = "agreement_discounts"

    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agreement_versions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("discount_revisions.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    version = relationship("AgreementVersion", back_populates="discounts")
    revision = relationship("DiscountRevision")


class SubscriptionRequest(Base, TimestampMixin):
    __tablename__ = "subscription_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_date: Mapped[date] = mapped_column(Date, nullable=False)
    desired_items: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    displayed_price_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    based_on_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ('PAUSE', 'RESUME', 'RENEW', 'EARLY_CLOSE', 'ADDON_CHANGE')",
            name="ck_subscription_requests_type",
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')",
            name="ck_subscription_requests_status",
        ),
    )

    subscription = relationship("Subscription", back_populates="requests", foreign_keys=[subscription_id])
    requester = relationship("User", foreign_keys=[requested_by])
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    term_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_terms.id", ondelete="RESTRICT"),
        nullable=True,
    )
    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_requests.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    agreement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agreement_versions.id", ondelete="RESTRICT"),
        nullable=True,
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    subscription = relationship("Subscription", back_populates="events", foreign_keys=[subscription_id])
    term = relationship("SubscriptionTerm")
    request = relationship("SubscriptionRequest")
    actor = relationship("User")


class SubscriptionPause(Base):
    __tablename__ = "subscription_pauses"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_terms.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    resumed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    original_expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    pause_event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_events.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    resume_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_events.id", ondelete="RESTRICT"),
        unique=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("resumed_date IS NULL OR resumed_date > start_date", name="ck_sub_pauses_resumed_gt_start"),
        Index(
            "uq_subscription_pauses_one_open",
            "term_id",
            unique=True,
            postgresql_where=text("resumed_date IS NULL"),
        ),
    )

    term = relationship("SubscriptionTerm", back_populates="pauses", foreign_keys=[term_id])
    pause_event = relationship("SubscriptionEvent", foreign_keys=[pause_event_id])
    resume_event = relationship("SubscriptionEvent", foreign_keys=[resume_event_id])
