import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.contracts import ordering
from app.api.deps import get_current_db, get_current_user
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.payments import Payment
from app.models.users import User
from app.services import payments as service
from app.services.payment_documents import render_payment_receipt

router = APIRouter()


@router.get("")
def list_payments(search: str = Query("", max_length=200), method: str | None = Query(None, pattern="^(CASH|BANK_TRANSFER|UPI|CARD|CHEQUE|OTHER)$"),
                   date_from: date | None = None, date_to: date | None = None,
                   invoice_id: uuid.UUID | None = None, customer_id: uuid.UUID | None = None,
                   sort: str = Query("payment_date", pattern="^(payment_date|amount|created_at)$"), descending: bool = True,
                   page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                   db: Session = Depends(get_current_db), actor: User = Depends(get_current_user)):
    if date_from and date_to and date_to < date_from:
        service.fail("The payment date range must end on or after its start.", 422)
    query = select(Payment).join(Invoice)
    if actor.role == "CUSTOMER":
        query = query.join(Customer, Customer.id == Invoice.customer_id).where(Customer.user_id == actor.id, Invoice.issued_at.is_not(None))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(Invoice.number.ilike(pattern) | Invoice.customer_name.ilike(pattern) | Payment.reference.ilike(pattern))
    if method:
        query = query.where(Payment.method == method)
    if date_from:
        query = query.where(Payment.payment_date >= date_from)
    if date_to:
        query = query.where(Payment.payment_date <= date_to)
    if invoice_id:
        query = query.where(Payment.invoice_id == invoice_id)
    if customer_id:
        query = query.where(Invoice.customer_id == customer_id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.options(selectinload(Payment.invoice), selectinload(Payment.recorder))
        .order_by(*ordering(sort, descending, {"payment_date": Payment.payment_date, "amount": Payment.amount, "created_at": Payment.created_at}, Payment.id))
        .offset((page - 1) * page_size).limit(page_size))
    return {"items": [service.payment_response(payment, actor) for payment in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/{payment_id}")
def get_payment(payment_id: uuid.UUID, db: Session = Depends(get_current_db), actor: User = Depends(get_current_user)):
    return service.payment_response(service.load_payment(db, payment_id, actor), actor)


@router.get("/{payment_id}/receipt")
def payment_receipt(payment_id: uuid.UUID, db: Session = Depends(get_current_db), actor: User = Depends(get_current_user)):
    payment = service.load_payment(db, payment_id, actor)
    return Response(render_payment_receipt(payment), media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="receipt-{payment.id}.pdf"',
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
