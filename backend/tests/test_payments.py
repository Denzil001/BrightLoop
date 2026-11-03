from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import uuid

import pytest
from pypdf import PdfReader
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from app.core.datetime_utils import get_business_today
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.payments import Payment
from test_invoices import command, generate
from test_subscriptions import draft_data, headers


def payload(**patch):
    return {"amount": "1000.00", "method": "BANK_TRANSFER", "payment_date": get_business_today().isoformat(),
            "note": "First installment received", "reference": "TRANSFER-123", "request_key": uuid.uuid4().hex, **patch}


def issue(db, client, admin_auth, draft_data):
    invoice = generate(db, admin_auth, draft_data)
    confirmed, _ = command(client, admin_auth, invoice, "CONFIRM")
    assert confirmed.status_code == 200
    return invoice


def test_partial_final_retry_and_balance_reconciliation(db, client, admin_auth, staff_auth, customer_auth, draft_data):
    invoice = issue(db, client, admin_auth, draft_data)
    url = f"/api/v1/invoices/{invoice.id}/payments"
    request = payload()
    first = client.post(url, json=request, headers=headers(staff_auth))
    assert first.status_code == 201, first.text
    assert first.json()["invoice"]["state"] == "PARTIALLY_PAID"
    assert first.json()["invoice"]["remaining"] == "416.00"
    replay = client.post(url, json={**request, "amount": "1000"}, headers=headers(staff_auth))
    assert replay.status_code == 201, replay.text
    assert replay.json()["payment"]["id"] == first.json()["payment"]["id"]
    assert db.scalar(select(func.count()).select_from(Payment)) == 1
    conflict = client.post(url, json={**request, "amount": "900.00"}, headers=headers(staff_auth))
    assert conflict.status_code == 409
    overpay = client.post(url, json=payload(amount="417.00"), headers=headers(admin_auth))
    assert overpay.status_code == 422
    assert "416.00" in overpay.text
    final = client.post(url, json=payload(amount="416.00", note="Final installment received"), headers=headers(admin_auth))
    assert final.status_code == 201, final.text
    assert final.json()["invoice"]["state"] == "PAID"
    assert final.json()["invoice"]["remaining"] == "0.00"
    assert final.json()["invoice"]["paid"] == "1416.00"
    assert db.scalar(select(func.sum(Payment.amount))) == Decimal("1416.00")
    assert client.post(url, json=request, headers=headers(staff_auth)).status_code == 201  # replay still succeeds after settlement
    forbidden, _ = command(client, admin_auth, invoice, "CANCEL", reason="Cannot erase settlement")
    assert forbidden.status_code == 409
    own = client.get(f"/api/v1/invoices/{invoice.id}", headers=headers(customer_auth)).json()
    assert own["remaining"] == "0.00" and own["paid"] == "1416.00"


@pytest.mark.parametrize("patch", [{"amount": "0"}, {"amount": "-1"}, {"amount": "1.001"},
    {"amount": "NaN"}, {"method": "GATEWAY"}, {"note": "  "}, {"request_key": "        "},
    {"payment_date": (get_business_today() + timedelta(days=1)).isoformat()}, {"recorded_by": str(uuid.uuid4())}])
def test_invalid_payment_input_is_rejected(db, client, admin_auth, draft_data, patch):
    invoice = issue(db, client, admin_auth, draft_data)
    response = client.post(f"/api/v1/invoices/{invoice.id}/payments", json=payload(**patch), headers=headers(admin_auth))
    assert response.status_code == 422, response.text
    assert db.scalar(select(func.count()).select_from(Payment)) == 0


def test_draft_cancelled_and_customer_payment_writes_forbidden(db, client, admin_auth, customer_auth, draft_data):
    invoice = generate(db, admin_auth, draft_data)
    url = f"/api/v1/invoices/{invoice.id}/payments"
    assert client.post(url, json=payload(), headers=headers(customer_auth)).status_code == 403
    assert client.post(url, json=payload(), headers=headers(admin_auth)).status_code == 409
    command(client, admin_auth, invoice, "CANCEL", reason="Cancelled draft")
    assert client.post(url, json=payload(), headers=headers(admin_auth)).status_code == 409


def test_customer_ledger_receipt_and_internal_metadata_isolation(db, client, admin_auth, customer_auth, draft_data):
    invoice = issue(db, client, admin_auth, draft_data)
    response = client.post(f"/api/v1/invoices/{invoice.id}/payments", json=payload(), headers=headers(admin_auth))
    payment_id = response.json()["payment"]["id"]
    own = client.get(f"/api/v1/payments/{payment_id}", headers=headers(customer_auth))
    assert own.status_code == 200
    assert own.json()["note"] == "First installment received"
    for internal in ("recorded_by", "recorded_at", "request_key", "request_hash"):
        assert internal not in own.json()
    listing = client.get("/api/v1/payments?method=BANK_TRANSFER&search=TRANSFER-123", headers=headers(customer_auth)).json()
    assert listing["total"] == 1
    receipt = client.get(f"/api/v1/payments/{payment_id}/receipt", headers=headers(customer_auth))
    assert receipt.status_code == 200
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(receipt.content)).pages)
    assert "INR 1,000.00" in text and invoice.number in text
    Path("test-results").mkdir(exist_ok=True)
    Path("test-results/payment-receipt.pdf").write_bytes(receipt.content)
    other = Customer(name="Different account", email_normalized="payment_other@brightloop.test")
    db.add(other)
    db.commit()
    alien = issue(db, client, admin_auth, {**draft_data, "customer_id": str(other.id)})
    payment = client.post(f"/api/v1/invoices/{alien.id}/payments", json=payload(), headers=headers(admin_auth)).json()["payment"]
    assert client.get(f"/api/v1/payments/{payment['id']}", headers=headers(customer_auth)).status_code == 404
    assert client.get(f"/api/v1/payments/{payment['id']}/receipt", headers=headers(customer_auth)).status_code == 404


@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_postgresql_payment_ledger_is_immutable(db, client, admin_auth, draft_data, operation):
    invoice = issue(db, client, admin_auth, draft_data)
    response = client.post(f"/api/v1/invoices/{invoice.id}/payments", json=payload(), headers=headers(admin_auth))
    payment_id = uuid.UUID(response.json()["payment"]["id"])
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            if operation == "UPDATE":
                db.execute(update(Payment).where(Payment.id == payment_id).values(amount=Decimal("1.00")))
            else:
                db.execute(delete(Payment).where(Payment.id == payment_id))
    assert db.get(Payment, payment_id).amount == Decimal("1000.00")
