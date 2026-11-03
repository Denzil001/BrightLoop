import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.contracts import created_location
from app.api.deps import get_current_db, get_current_user, require_role, verify_csrf, verify_origin
from app.core.datetime_utils import get_business_today
from app.models.audit import AuditEvent
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.payments import Payment
from app.models.subscriptions import Subscription
from app.models.users import User
from app.schemas.invoices import InvoiceCommand, InvoiceMetadataUpdate
from app.schemas.payments import PaymentCreate
from app.services import payments as payment_service
from app.services import invoices as service
from app.services.invoice_documents import render_invoice_pdf
from app.services.invoice_delivery import send_invoice

router = APIRouter()
mutation = [Depends(verify_csrf), Depends(verify_origin)]


def invoice_detail(db, invoice, user):
    result = service.invoice_summary(invoice, service.paid_amount(db, invoice.id))
    result.update({"issuer_name": invoice.issuer_name, "issuer_tax_id": invoice.issuer_tax_id,
        "issuer_address": invoice.issuer_address, "customer_email": invoice.customer_email,
        "customer_company": invoice.customer_company, "customer_address": invoice.customer_address,
        "issued_at": invoice.issued_at, "cancelled_at": invoice.cancelled_at,
        "full_period_end": invoice.full_period_end, "service_days": invoice.service_days,
        "full_period_days": invoice.full_period_days,
        "lines": [{"id": line.id, "ordinal": line.ordinal, "description": line.snapshot_description,
            "quantity": line.quantity, "unit_price": str(line.unit_price), "subtotal": str(line.subtotal),
            "discount": str(line.discount_amount), "tax": str(line.tax_amount), "total": str(line.total),
            "taxes": [{"name": tax.snapshot_name, "rate": str(tax.snapshot_rate),
                       "taxable_base": str(tax.taxable_base), "amount": str(tax.amount)} for tax in line.taxes]}
            for line in sorted(invoice.lines, key=lambda line: line.ordinal)]})
    result["payments"] = [payment_service.payment_response(payment, user) for payment in db.scalars(
        select(Payment).where(Payment.invoice_id == invoice.id)
        .order_by(Payment.payment_date.desc(), Payment.created_at.desc(), Payment.id).limit(20))]
    result["payment_count"] = db.scalar(select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice.id))
    if user.role != "CUSTOMER":
        result["cancel_reason"] = invoice.cancel_reason
        result["delivery_attempts"] = [{"id": attempt.id, "status": attempt.status, "attempted_at": attempt.attempted_at,
                                        "safe_error_code": attempt.safe_error_code} for attempt in invoice.email_attempts]
        result["history"] = [{"id": event.id, "action": event.action, "timestamp": event.timestamp,
                               "reason": (event.payload or {}).get("reason")}
                              for event in db.scalars(select(AuditEvent).where(AuditEvent.target_type == "invoice",
                                  AuditEvent.target_id == str(invoice.id)).order_by(AuditEvent.timestamp, AuditEvent.id))]
    return result


@router.get("")
def list_invoices(search: str = Query("", max_length=200), state: str | None = Query(None, pattern="^(DRAFT|CONFIRMED|PARTIALLY_PAID|PAID|CANCELLED)$"),
                   overdue: bool = False, outstanding: bool = False, customer_id: uuid.UUID | None = None, subscription_id: uuid.UUID | None = None,
                   issue_from: date | None = None, issue_to: date | None = None,
                   due_from: date | None = None, due_to: date | None = None,
                   sort: str = Query("invoice_date", pattern="^(invoice_date|due_date|number|total)$"), descending: bool = True,
                   page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_current_db), user: User = Depends(get_current_user)):
    for first, last in ((issue_from, issue_to), (due_from, due_to)):
        if first and last and last < first:
            service.fail("The end of a date range must be on or after its start.", 422)
    paid = select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == Invoice.id).correlate(Invoice).scalar_subquery()
    query = select(Invoice, paid).join(Subscription, Subscription.id == Invoice.subscription_id)
    if user.role == "CUSTOMER":
        query = query.join(Customer, Customer.id == Invoice.customer_id).where(Customer.user_id == user.id, Invoice.issued_at.is_not(None))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(Invoice.number.ilike(pattern) | Invoice.customer_name.ilike(pattern) | Subscription.number.ilike(pattern))
    if state:
        query = query.where(Invoice.state == state)
    if customer_id:
        query = query.where(Invoice.customer_id == customer_id)
    if subscription_id:
        query = query.where(Invoice.subscription_id == subscription_id)
    if overdue:
        query = query.where(Invoice.issued_at.is_not(None), Invoice.state != "CANCELLED", Invoice.total > paid, Invoice.due_date < get_business_today())
    if outstanding:
        query = query.where(Invoice.issued_at.is_not(None), Invoice.state != "CANCELLED", Invoice.total > paid)
    for column, first, last in ((Invoice.invoice_date, issue_from, issue_to), (Invoice.due_date, due_from, due_to)):
        if first:
            query = query.where(column >= first)
        if last:
            query = query.where(column <= last)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    order = getattr(Invoice, sort)
    rows = db.execute(query.order_by(order.desc() if descending else order.asc(), Invoice.id)
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [service.invoice_summary(invoice, amount) for invoice, amount in rows],
            "page": page, "page_size": page_size, "total": total}


@router.get("/{invoice_id}")
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_current_db), user: User = Depends(get_current_user)):
    return invoice_detail(db, service.load_invoice(db, invoice_id, user), user)


@router.post("/{invoice_id}/commands", dependencies=mutation)
def invoice_command(invoice_id: uuid.UUID, payload: InvoiceCommand, db: Session = Depends(get_current_db),
                    user: User = Depends(require_role(["ADMIN", "STAFF"]))):
    invoice = service.load_invoice(db, invoice_id, user, lock=True)
    service.command_invoice(db, invoice, payload, user)
    db.commit()
    return invoice_detail(db, invoice, user)


@router.patch("/{invoice_id}/draft-metadata", dependencies=mutation)
def invoice_metadata(invoice_id: uuid.UUID, payload: InvoiceMetadataUpdate, db: Session = Depends(get_current_db),
                     user: User = Depends(require_role(["ADMIN", "STAFF"]))):
    invoice = service.load_invoice(db, invoice_id, user, lock=True)
    service.update_metadata(db, invoice, payload, user)
    db.commit()
    return invoice_detail(db, invoice, user)


@router.get("/{invoice_id}/document")
def invoice_document(invoice_id: uuid.UUID, download: bool = False, db: Session = Depends(get_current_db),
                      user: User = Depends(get_current_user)):
    invoice = service.load_invoice(db, invoice_id, user)
    document = render_invoice_pdf(invoice)
    return Response(document, media_type="application/pdf", headers={
        "Content-Disposition": f'{"attachment" if download else "inline"}; filename="{invoice.number}.pdf"',
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/{invoice_id}/send", dependencies=mutation)
def invoice_send(invoice_id: uuid.UUID, db: Session = Depends(get_current_db),
                  user: User = Depends(require_role(["ADMIN", "STAFF"]))):
    return send_invoice(db, service.load_invoice(db, invoice_id, user, lock=True), user)


@router.post("/{invoice_id}/payments", status_code=201, dependencies=mutation)
def record_invoice_payment(response: Response, invoice_id: uuid.UUID, payload: PaymentCreate, db: Session = Depends(get_current_db),
                            user: User = Depends(require_role(["ADMIN", "STAFF"]))):
    payment = payment_service.record_payment(db, invoice_id, payload, user)
    db.commit()
    invoice = service.load_invoice(db, invoice_id, user)
    created_location(response, f"payments/{payment.id}")
    return {"payment": payment_service.payment_response(payment, user), "invoice": invoice_detail(db, invoice, user)}
