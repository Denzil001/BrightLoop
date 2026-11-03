"""Invoice authority and state changes; persisted payments determine balances."""
from decimal import Decimal

from sqlalchemy import func, select

from app.core.datetime_utils import get_business_now, get_business_today
from app.models.audit import AuditEvent
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.payments import Payment
from app.services.change_requests import lookup_receipt, record_receipt
from app.services.subscriptions import fail


def paid_amount(db, invoice_id):
    return db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice_id)) or Decimal("0.00")


def load_invoice(db, invoice_id, actor, lock=False):
    query = select(Invoice).where(Invoice.id == invoice_id)
    if actor.role == "CUSTOMER":
        query = query.join(Customer, Customer.id == Invoice.customer_id).where(
            Customer.user_id == actor.id, Invoice.issued_at.is_not(None))
    if lock:
        query = query.with_for_update(of=Invoice).execution_options(populate_existing=True)
    invoice = db.scalar(query)
    if invoice is None:
        fail("Invoice not found.", 404)
    return invoice


def balance(invoice, paid):
    return max(Decimal("0.00"), invoice.total - paid) if invoice.issued_at and invoice.state != "CANCELLED" else Decimal("0.00")


def invoice_summary(invoice, paid):
    remaining = balance(invoice, paid)
    return {"id": invoice.id, "number": invoice.number, "subscription_id": invoice.subscription_id,
        "customer_id": invoice.customer_id, "customer_name": invoice.customer_name, "state": invoice.state,
        "period_start": invoice.period_start, "period_end": invoice.period_end,
        "invoice_date": invoice.invoice_date, "due_date": invoice.due_date, "currency": invoice.currency,
        "subtotal": str(invoice.subtotal), "discount_total": str(invoice.discount_total), "tax_total": str(invoice.tax_total),
        "total": str(invoice.total), "paid": str(paid), "remaining": str(remaining),
        "overdue": remaining > 0 and invoice.due_date < get_business_today(), "version": invoice.version}


def command_invoice(db, invoice, payload, actor):
    operation = f"invoice:{invoice.id}"
    receipt, digest = lookup_receipt(db, actor, operation, payload)
    if receipt:
        return
    if invoice.version != payload.expected_version:
        fail("This invoice changed. Refresh before continuing.")
    paid = paid_amount(db, invoice.id)
    if payload.action == "CONFIRM":
        if invoice.state != "DRAFT":
            fail("Only draft invoices can be confirmed.")
        invoice.state = "PAID" if invoice.total == 0 else "CONFIRMED"
        invoice.issued_at = get_business_now()
    elif payload.action == "CANCEL":
        if invoice.state not in ("DRAFT", "CONFIRMED") or paid != 0:
            fail("Only completely unpaid draft or confirmed invoices can be cancelled.")
        if not payload.reason or not payload.reason.strip():
            fail("Give a reason for cancelling this invoice.", 422)
        invoice.state = "CANCELLED"
        invoice.cancelled_at = get_business_now()
        invoice.cancel_reason = payload.reason.strip()
    invoice.version += 1
    db.add(AuditEvent(actor_id=actor.id, action=f"INVOICE_{payload.action}", target_type="invoice", target_id=str(invoice.id),
                      payload={"reason": payload.reason} if payload.reason else None))
    record_receipt(db, actor, operation, payload, digest, invoice, result_type="invoice")
    db.flush()


def update_metadata(db, invoice, payload, actor):
    if invoice.state != "DRAFT":
        fail("Only draft invoice billing metadata can be corrected.")
    if invoice.version != payload.expected_version:
        fail("This invoice changed. Refresh before saving.")
    if not payload.reason.strip():
        fail("Give a reason for the correction.", 422)
    if payload.due_date and payload.due_date < invoice.invoice_date:
        fail("The due date cannot precede the invoice date.", 422)
    changes = payload.model_dump(exclude={"expected_version", "reason"}, exclude_unset=True)
    if any(value is None for key, value in changes.items() if key not in ("customer_company",)):
        fail("Required billing metadata cannot be cleared.", 422)
    for key, value in changes.items():
        setattr(invoice, key, value)
    invoice.version += 1
    db.add(AuditEvent(actor_id=actor.id, action="INVOICE_METADATA_CORRECTED", target_type="invoice", target_id=str(invoice.id),
                      payload={"reason": payload.reason.strip(), "fields": sorted(changes)}))
