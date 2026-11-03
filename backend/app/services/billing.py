"""One period transaction: lock, reconstruct, calculate, snapshot, consume, advance.

The caller commits each result independently; failed work must be rolled back
before recording a safe failed outcome. Catalog prices/taxes are never read here.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import select

from app.core.config import get_settings
from app.core.datetime_utils import get_business_now
from app.models.audit import AuditEvent
from app.models.billing import BillingOutcome
from app.models.discounts import DiscountRedemption
from app.models.invoices import Invoice, InvoiceLine, InvoiceLineDiscount, InvoiceLineTax
from app.models.subscriptions import Subscription, SubscriptionEvent, SubscriptionPause, SubscriptionTerm
from app.services.billing_periods import agreement_for_period, periods
from app.services.discount_context import load_terms, resolve_revisions
from app.services.financial_calculator import Charge, PricingError, Tax, calculate
from app.services.lifecycle import apply_event


@dataclass(frozen=True)
class PeriodResult:
    state: str
    invoice_id: uuid.UUID | None = None
    period_start: date | None = None


class BillingFailure(Exception):
    def __init__(self, period_start, safe_code):
        self.period_start = period_start
        self.safe_code = safe_code
        super().__init__(safe_code)


def _first_unprocessed(db, subscription_id, existing, before=None):
    for period in periods(db, subscription_id):
        if before is not None and period.start >= before:
            return None
        if period.start not in existing:
            return period
    return None


def process_next_period(db, subscription_id, as_of, run_id=None, actor_id=None):
    subscription = db.scalar(select(Subscription).where(Subscription.id == subscription_id)
                             .with_for_update().execution_options(populate_existing=True))
    if subscription is None:
        raise PricingError("Subscription not found.")
    existing = {invoice.period_start: invoice for invoice in db.scalars(
        select(Invoice).where(Invoice.subscription_id == subscription.id))}
    if subscription.state == "CONFIRMED":
        first = next(periods(db, subscription.id), None)
        if first and first.start <= as_of:
            subscription.state = "ACTIVE"
            subscription.version += 1
            db.add(SubscriptionEvent(subscription_id=subscription.id, term_id=first.term_id, action="ACTIVATE",
                effective_date=first.start, applied_at=get_business_now(), actor_id=actor_id,
                payload={"source": "BILLING_RECONCILIATION"}))
    pending = db.scalars(select(SubscriptionEvent).where(SubscriptionEvent.subscription_id == subscription.id,
        SubscriptionEvent.applied_at.is_(None), SubscriptionEvent.effective_date <= as_of)
        .order_by(SubscriptionEvent.effective_date, SubscriptionEvent.id)).all()
    candidate = None
    for event in pending:
        candidate = _first_unprocessed(db, subscription.id, existing, before=event.effective_date)
        if candidate:
            break  # older owed service must commit before this boundary event
        apply_event(db, subscription, event, as_of=as_of)
    if candidate is None:
        candidate = _first_unprocessed(db, subscription.id, existing)
    if candidate is None or candidate.start > as_of:
        subscription.next_billing_date = candidate.start if candidate else None
        latest = max((invoice for start, invoice in existing.items() if start <= as_of),
                     key=lambda invoice: invoice.period_start, default=None)
        result = PeriodResult("EXISTING", latest.id, latest.period_start) if latest else PeriodResult("IDLE")
    else:
        try:
            invoice = _create_invoice(db, subscription, candidate, as_of, actor_id)
        except Exception as exc:
            raise BillingFailure(candidate.start, "INVALID_AGREEMENT" if isinstance(exc, PricingError) else "PERIOD_WRITE_FAILED") from exc
        existing[candidate.start] = invoice
        # Cursor is a cache of the earliest unprocessed historical/future boundary.
        # The durable period identity is authoritative on every recovery run.
        next_period = _first_unprocessed(db, subscription.id, existing)
        subscription.next_billing_date = next_period.start if next_period else None
        subscription.version += 1
        result = PeriodResult("CREATED", invoice.id, candidate.start)
    # Closing the current service state never removes durable historical periods.
    # Wait until the backlog is complete and respect the frozen term policy.
    term = db.scalar(select(SubscriptionTerm).where(SubscriptionTerm.subscription_id == subscription.id)
                     .order_by(SubscriptionTerm.sequence.desc()).limit(1))
    open_pause = term and db.scalar(select(SubscriptionPause.id).where(
        SubscriptionPause.term_id == term.id, SubscriptionPause.resumed_date.is_(None)).limit(1))
    if (term and term.auto_close_on_expiry and term.expiry_date <= as_of
            and subscription.state == "ACTIVE" and not open_pause
            and _first_unprocessed(db, subscription.id, existing) is None):
        subscription.state = "CLOSED"
        subscription.next_billing_date = None
        subscription.version += 1
        db.add(SubscriptionEvent(subscription_id=subscription.id, term_id=term.id,
            action="AUTO_CLOSE", effective_date=term.expiry_date, applied_at=get_business_now(),
            actor_id=actor_id, payload={"source": "BILLING_RECONCILIATION"}))
        db.add(AuditEvent(actor_id=actor_id, action="SUBSCRIPTION_AUTO_CLOSED", target_type="subscription",
            target_id=str(subscription.id), payload={"expiry_date": term.expiry_date.isoformat()}))
    recorded_created = run_id and result.state == "EXISTING" and db.scalar(select(BillingOutcome.id).where(
        BillingOutcome.run_id == run_id, BillingOutcome.invoice_id == result.invoice_id, BillingOutcome.state == "CREATED").limit(1))
    if run_id and result.invoice_id and not recorded_created:
        db.add(BillingOutcome(run_id=run_id, subscription_id=subscription.id, invoice_id=result.invoice_id,
                             period_start=result.period_start, state=result.state))
    db.flush()
    return result


def _create_invoice(db, subscription, period, as_of, actor_id):
    agreement = agreement_for_period(db, period)
    if agreement is None:
        raise PricingError("No accepted commercial version covers this historical service period.")
    lines = sorted(agreement.lines, key=lambda line: line.ordinal)
    charges = [Charge(line.ordinal, line.kind, line.product_id, line.quantity, line.unit_price,
                     tuple(Tax(tax.source_tax_id, tax.snapshot_name, tax.snapshot_rate) for tax in line.taxes))
               for line in lines]
    revisions = resolve_revisions(db, [], [discount.revision_id for discount in agreement.discounts], period.start)
    discounts = load_terms(db, revisions, period.start, lock_rules=True)
    result = calculate(charges, discounts, agreement.seat_quantity, period.service_days, period.full_days)
    settings, customer = get_settings(), subscription.customer
    invoice = Invoice(number=f"INV-{uuid.uuid4().hex.upper()}", subscription_id=subscription.id,
        term_id=period.term_id, agreement_id=agreement.id, customer_id=subscription.customer_id,
        period_start=period.start, period_end=period.end, full_period_end=period.full_end,
        service_days=period.service_days, full_period_days=period.full_days,
        invoice_date=as_of, due_date=as_of + timedelta(days=agreement.payment_term_days), currency=agreement.currency,
        state="DRAFT", subtotal=result.subtotal, discount_total=result.discount, tax_total=result.tax, total=result.total,
        issuer_name=settings.COMPANY_NAME, issuer_tax_id=settings.COMPANY_TAX_ID,
        issuer_address=settings.issuer_address_dict, customer_name=customer.name,
        customer_email=customer.email_normalized, customer_company=customer.company,
        customer_address={key: getattr(customer, f"billing_{key}") for key in (
            "address_line1", "address_line2", "city", "state", "postal_code", "country")})
    db.add(invoice)
    db.flush()
    redemptions = {}
    for discount in result.applied:
        amount = sum((line.allocations.get(discount.revision_id, Decimal("0.00")) for line in result.lines), Decimal("0.00"))
        redemption = DiscountRedemption(rule_id=discount.rule_id, revision_id=discount.revision_id,
                                        invoice_id=invoice.id, amount=amount)
        db.add(redemption)
        db.flush()
        redemptions[discount.revision_id] = redemption
    for source, calculated in zip(lines, result.lines):
        line = InvoiceLine(invoice_id=invoice.id, ordinal=source.ordinal, agreement_line_id=source.id,
            snapshot_description=source.snapshot_name + (f" ({source.snapshot_variant_name})" if source.snapshot_variant_name else ""),
            snapshot_product_name=source.snapshot_name if source.product_id else None,
            snapshot_variant_name=source.snapshot_variant_name, quantity=source.quantity,
            unit_price=source.unit_price, subtotal=calculated.subtotal, discount_amount=calculated.discount,
            tax_amount=calculated.tax, total=calculated.total)
        db.add(line)
        db.flush()
        for tax, base, amount in calculated.taxes:
            db.add(InvoiceLineTax(invoice_line_id=line.id, source_tax_id=tax.id,
                snapshot_name=tax.name, snapshot_rate=tax.rate, taxable_base=base, amount=amount))
        for revision_id, amount in calculated.allocations.items():
            db.add(InvoiceLineDiscount(invoice_line_id=line.id, invoice_id=invoice.id,
                                      redemption_id=redemptions[revision_id].id, allocated_amount=amount))
    db.add(AuditEvent(actor_id=actor_id, action="INVOICE_GENERATED", target_type="invoice", target_id=str(invoice.id),
                      payload={"subscription_id": str(subscription.id), "period_start": period.start.isoformat()}))
    db.flush()
    return invoice
