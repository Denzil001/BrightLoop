"""Serialized, immutable payments; retry keys describe normalized financial intent."""
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.audit import AuditEvent
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.payments import Payment
from app.services.invoices import load_invoice, paid_amount
from app.services.subscriptions import fail


def request_hash(invoice_id, payload):
    intent = {"invoice_id": str(invoice_id), "amount": f"{payload.amount:.2f}", "method": payload.method,
              "payment_date": payload.payment_date.isoformat(), "note": payload.note, "reference": payload.reference}
    return hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _existing_result(existing, digest):
    if existing.request_hash != digest:
        fail("This payment request key was already used for different details. Refresh the invoice before recording another payment.")
    return existing


def record_payment(db, invoice_id, payload, actor):
    if actor.role not in ("ADMIN", "STAFF") or not actor.active:
        fail("Only active operational staff can record payments.", 403)
    invoice = load_invoice(db, invoice_id, actor, lock=True)
    digest = request_hash(invoice.id, payload)
    existing = db.scalar(select(Payment).where(Payment.request_key == payload.request_key))
    if existing:
        return _existing_result(existing, digest)
    if invoice.issued_at is None or invoice.state not in ("CONFIRMED", "PARTIALLY_PAID"):
        fail("Payments can only be recorded against an issued invoice with an outstanding balance.")
    paid = paid_amount(db, invoice.id)
    remaining = invoice.total - paid
    if payload.amount > remaining:
        fail(f"The payment exceeds the current outstanding balance of {invoice.currency} {remaining:.2f}.", 422)
    payment = Payment(invoice_id=invoice.id, amount=payload.amount, method=payload.method,
        payment_date=payload.payment_date, note=payload.note, reference=payload.reference,
        recorded_by=actor.id, request_key=payload.request_key, request_hash=digest)
    try:
        # Invoice lock is outside this savepoint. A global key collision on a
        # different invoice rolls back only this attempted payment/status write.
        with db.begin_nested():
            db.add(payment)
            invoice.state = "PAID" if paid + payload.amount == invoice.total else "PARTIALLY_PAID"
            invoice.version += 1
            db.flush()
            db.add(AuditEvent(actor_id=actor.id, action="PAYMENT_RECORDED", target_type="invoice", target_id=str(invoice.id),
                              payload={"payment_id": str(payment.id), "amount": f"{payment.amount:.2f}"}))
            db.flush()
    except IntegrityError:
        existing = db.scalar(select(Payment).where(Payment.request_key == payload.request_key))
        if existing:
            return _existing_result(existing, digest)
        raise
    return payment


def load_payment(db, payment_id, actor):
    query = select(Payment).join(Invoice).where(Payment.id == payment_id)
    if actor.role == "CUSTOMER":
        query = query.join(Customer, Customer.id == Invoice.customer_id).where(Customer.user_id == actor.id, Invoice.issued_at.is_not(None))
    payment = db.scalar(query)
    if payment is None:
        fail("Payment not found.", 404)
    return payment


def payment_response(payment, actor):
    invoice = payment.invoice
    result = {"id": payment.id, "invoice_id": invoice.id, "invoice_number": invoice.number,
        "customer_id": invoice.customer_id, "customer_name": invoice.customer_name,
        "amount": str(payment.amount), "currency": invoice.currency, "method": payment.method,
        "payment_date": payment.payment_date, "note": payment.note, "reference": payment.reference}
    if actor.role != "CUSTOMER":
        result["recorded_by"] = payment.recorder.name
        result["recorded_at"] = payment.created_at
    return result
