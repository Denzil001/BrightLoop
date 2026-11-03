from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from conftest import test_engine
from app.core.datetime_utils import get_business_today
from app.models.invoices import Invoice
from app.models.payments import Payment
from app.models.users import User
from app.schemas.invoices import InvoiceCommand
from app.schemas.payments import PaymentCreate
from app.services.invoices import command_invoice, load_invoice
from app.services.payments import record_payment
from test_billing_concurrency import committed_case, process


def issue_invoices(ids):
    invoices = []
    for subscription_id in ids["subscriptions"]:
        result = process(subscription_id)
        with Session(test_engine) as db:
            invoice = db.get(Invoice, result.invoice_id)
            actor = db.get(User, ids["actor"])
            command_invoice(db, invoice, InvoiceCommand(action="CONFIRM", expected_version=invoice.version,
                                                        request_key=uuid.uuid4().hex), actor)
            db.commit()
            invoices.append((invoice.id, invoice.total, invoice.version))
    return invoices


def write_payment(arguments):
    invoice_id, actor_id, amount, key = arguments
    with Session(test_engine) as db:
        try:
            payment = record_payment(db, invoice_id, PaymentCreate(amount=amount, method="UPI",
                payment_date=get_business_today(), note="Concurrent payment received", request_key=key), db.get(User, actor_id))
            db.commit()
            return payment.id
        except HTTPException as exc:
            db.rollback()
            return f"rejected:{exc.status_code}"


def test_two_concurrent_partial_payments_serialize_and_reconcile():
    with committed_case(1) as ids:
        invoice_id, total, version = issue_invoices(ids)[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write_payment, [(invoice_id, ids["actor"], total / 2, uuid.uuid4().hex) for _ in range(2)]))
        assert all(isinstance(result, uuid.UUID) for result in results)
        with Session(test_engine) as db:
            assert db.scalar(select(func.sum(Payment.amount)).where(Payment.invoice_id == invoice_id)) == total
            invoice = db.get(Invoice, invoice_id)
            assert invoice.state == "PAID"
            assert invoice.version == version + 2


def test_simultaneous_full_payments_cannot_overpay():
    with committed_case(1) as ids:
        invoice_id, total, _ = issue_invoices(ids)[0]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write_payment, [(invoice_id, ids["actor"], total, uuid.uuid4().hex) for _ in range(2)]))
        assert sum(isinstance(result, uuid.UUID) for result in results) == 1
        with Session(test_engine) as db:
            assert db.scalar(select(func.sum(Payment.amount)).where(Payment.invoice_id == invoice_id)) == total
            assert db.scalar(select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice_id)) == 1


def test_concurrent_same_key_retries_return_one_payment():
    with committed_case(1) as ids:
        invoice_id, total, version = issue_invoices(ids)[0]
        key = uuid.uuid4().hex
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write_payment, [(invoice_id, ids["actor"], total, key)] * 2))
        assert isinstance(results[0], uuid.UUID)
        assert results[0] == results[1]
        with Session(test_engine) as db:
            assert db.get(Invoice, invoice_id).version == version + 1
            assert db.scalar(select(func.count()).select_from(Payment).where(Payment.request_key == key)) == 1


def test_global_key_collision_across_invoices_rolls_back_loser():
    with committed_case(2) as ids:
        invoices = issue_invoices(ids)
        key = uuid.uuid4().hex
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(write_payment, [(invoice_id, ids["actor"], Decimal("1.00"), key) for invoice_id, _, _ in invoices]))
        assert sum(isinstance(result, uuid.UUID) for result in results) == 1
        assert "rejected:409" in results
        with Session(test_engine) as db:
            assert db.scalar(select(func.count()).select_from(Payment).where(Payment.request_key == key)) == 1
            states = [db.get(Invoice, invoice_id).state for invoice_id, _, _ in invoices]
            assert sorted(states) == ["CONFIRMED", "PARTIALLY_PAID"]
            assert sorted(db.get(Invoice, invoice_id).version - version for invoice_id, _, version in invoices) == [0, 1]


def test_payment_and_cancellation_share_the_invoice_lock():
    with committed_case(1) as ids:
        invoice_id, total, _ = issue_invoices(ids)[0]

        def cancel():
            with Session(test_engine) as db:
                try:
                    actor = db.get(User, ids["actor"])
                    invoice = load_invoice(db, invoice_id, actor, lock=True)
                    command_invoice(db, invoice, InvoiceCommand(action="CANCEL", expected_version=invoice.version,
                        request_key=uuid.uuid4().hex, reason="Concurrent cancellation"), actor)
                    db.commit()
                    return "CANCELLED"
                except HTTPException as exc:
                    db.rollback()
                    return f"rejected:{exc.status_code}"

        with ThreadPoolExecutor(max_workers=2) as pool:
            payment_future = pool.submit(write_payment, (invoice_id, ids["actor"], total, uuid.uuid4().hex))
            cancellation_future = pool.submit(cancel)
            payment_result, cancel_result = payment_future.result(), cancellation_future.result()
        with Session(test_engine) as db:
            invoice = db.get(Invoice, invoice_id)
            paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice_id))
            if invoice.state == "CANCELLED":
                assert paid == 0 and isinstance(payment_result, str) and cancel_result == "CANCELLED"
            else:
                assert invoice.state == "PAID" and paid == total
                assert isinstance(payment_result, uuid.UUID) and cancel_result == "rejected:409"
