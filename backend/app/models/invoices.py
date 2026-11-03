import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    CHAR,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    number: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    term_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_terms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    agreement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agreement_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    full_period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    service_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    full_period_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(CHAR(3), default="INR", nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discount_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    tax_total: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    issuer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    issuer_tax_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    issuer_address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_company: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_address: Mapped[dict] = mapped_column(JSONB, nullable=False)
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    __table_args__ = (
        UniqueConstraint("subscription_id", "period_start", name="uq_invoices_subscription_period"),
        UniqueConstraint("id", "subscription_id", name="uq_invoices_id_sub"),
        CheckConstraint(
            "state IN ('DRAFT', 'CONFIRMED', 'PARTIALLY_PAID', 'PAID', 'CANCELLED')",
            name="ck_invoices_state",
        ),
        CheckConstraint("period_end > period_start", name="ck_invoices_period_end_gt_start"),
        CheckConstraint("service_days > 0 AND full_period_days >= service_days", name="ck_invoices_proration_days"),
        CheckConstraint("subtotal >= 0", name="ck_invoices_subtotal_nonneg"),
        CheckConstraint("discount_total >= 0", name="ck_invoices_discount_total_nonneg"),
        CheckConstraint("tax_total >= 0", name="ck_invoices_tax_total_nonneg"),
        CheckConstraint("total >= 0", name="ck_invoices_total_nonneg"),
        CheckConstraint(
            "total = subtotal - discount_total + tax_total",
            name="ck_invoices_total_identity",
        ),
        ForeignKeyConstraint(
            ["subscription_id", "customer_id"],
            ["subscriptions.id", "subscriptions.customer_id"],
            ondelete="RESTRICT",
            name="fk_invoices_sub_customer",
        ),
        ForeignKeyConstraint(
            ["term_id", "subscription_id"],
            ["subscription_terms.id", "subscription_terms.subscription_id"],
            ondelete="RESTRICT",
            name="fk_invoices_term_sub",
        ),
        ForeignKeyConstraint(
            ["agreement_id", "subscription_id"],
            ["agreement_versions.id", "agreement_versions.subscription_id"],
            ondelete="RESTRICT",
            name="fk_invoices_agreement_sub",
        ),
    )

    subscription = relationship("Subscription", back_populates="invoices", foreign_keys=[subscription_id])
    customer = relationship("Customer", back_populates="invoices", foreign_keys=[customer_id])
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan", foreign_keys="[InvoiceLine.invoice_id]")
    payments = relationship("Payment", back_populates="invoice", foreign_keys="[Payment.invoice_id]")
    discount_redemptions = relationship("DiscountRedemption", back_populates="invoice", foreign_keys="[DiscountRedemption.invoice_id]")
    email_attempts = relationship("EmailAttempt", back_populates="invoice", foreign_keys="[EmailAttempt.invoice_id]")


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    agreement_line_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agreement_lines.id", ondelete="RESTRICT"),
        nullable=True,
    )
    snapshot_description: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_product_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    snapshot_variant_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("invoice_id", "ordinal", name="uq_invoice_lines_ordinal"),
        # Target for composite foreign key in invoice_line_discounts
        UniqueConstraint("id", "invoice_id", name="uq_invoice_lines_id_invoice"),
        CheckConstraint("quantity > 0", name="ck_invoice_lines_qty_pos"),
        CheckConstraint("unit_price >= 0", name="ck_invoice_lines_unit_price_nonneg"),
        CheckConstraint("subtotal >= 0", name="ck_invoice_lines_subtotal_nonneg"),
        CheckConstraint("discount_amount >= 0", name="ck_invoice_lines_discount_nonneg"),
        CheckConstraint("tax_amount >= 0", name="ck_invoice_lines_tax_nonneg"),
        CheckConstraint("total >= 0", name="ck_invoice_lines_total_nonneg"),
        CheckConstraint("discount_amount <= subtotal", name="ck_invoice_lines_discount_lte_subtotal"),
        CheckConstraint("total = subtotal - discount_amount + tax_amount", name="ck_invoice_lines_total_identity"),
    )

    invoice = relationship("Invoice", back_populates="lines", foreign_keys=[invoice_id])
    agreement_line = relationship("AgreementLine", foreign_keys=[agreement_line_id])
    taxes = relationship("InvoiceLineTax", back_populates="line", cascade="all, delete-orphan", foreign_keys="[InvoiceLineTax.invoice_line_id]")
    discounts = relationship("InvoiceLineDiscount", back_populates="line", cascade="all, delete-orphan", foreign_keys="[InvoiceLineDiscount.invoice_line_id]")


class InvoiceLineTax(Base):
    __tablename__ = "invoice_line_taxes"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("invoice_lines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    source_tax_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tax_rules.id", ondelete="RESTRICT"),
        nullable=False,
    )
    snapshot_name: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_rate: Mapped[Decimal] = mapped_column(Numeric(7, 4), nullable=False)
    taxable_base: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("snapshot_rate >= 0 AND snapshot_rate <= 100", name="ck_inv_line_tax_rate"),
        CheckConstraint("taxable_base >= 0", name="ck_inv_line_taxable_base_nonneg"),
        CheckConstraint("amount >= 0", name="ck_inv_line_tax_amount_nonneg"),
    )

    line = relationship("InvoiceLine", back_populates="taxes", foreign_keys=[invoice_line_id])
    source_tax = relationship("TaxRule")


class InvoiceLineDiscount(Base):
    __tablename__ = "invoice_line_discounts"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_line_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("invoice_lines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    redemption_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("discount_redemptions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("invoices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint("allocated_amount >= 0", name="ck_inv_line_discount_amount_nonneg"),
        ForeignKeyConstraint(
            ["invoice_line_id", "invoice_id"],
            ["invoice_lines.id", "invoice_lines.invoice_id"],
            ondelete="RESTRICT",
            name="fk_line_discounts_line_invoice",
        ),
        ForeignKeyConstraint(
            ["redemption_id", "invoice_id"],
            ["discount_redemptions.id", "discount_redemptions.invoice_id"],
            ondelete="RESTRICT",
            name="fk_line_discounts_redemption_invoice",
        ),
    )

    line = relationship("InvoiceLine", back_populates="discounts", foreign_keys=[invoice_line_id])
    redemption = relationship("DiscountRedemption", foreign_keys=[redemption_id])
    invoice = relationship("Invoice", foreign_keys=[invoice_id])
