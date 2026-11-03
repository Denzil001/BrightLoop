from datetime import date, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import func, select

from app.core.datetime_utils import get_business_today
from app.models.catalog import Plan
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.payments import Payment
from app.services.billing import process_next_period
from test_billing import contract
from test_subscriptions import draft_data, headers


def generate(db, admin_auth, draft_data):
    subscription = contract(db, admin_auth["user"], draft_data)
    result = process_next_period(db, subscription.id, date(2025, 1, 31))
    db.commit()
    return db.get(Invoice, result.invoice_id)


def command(client, auth, invoice, action, **patch):
    payload = {"action": action, "expected_version": invoice.version, "request_key": uuid.uuid4().hex, **patch}
    response = client.post(f"/api/v1/invoices/{invoice.id}/commands", json=payload, headers=headers(auth))
    return response, payload


def test_customer_visibility_commands_and_snapshot_isolation(db, client, admin_auth, customer_auth, staff_auth, draft_data):
    invoice = generate(db, admin_auth, draft_data)
    url = f"/api/v1/invoices/{invoice.id}"
    assert client.get(url, headers=headers(customer_auth)).status_code == 404
    assert client.get("/api/v1/invoices", headers=headers(customer_auth)).json()["total"] == 0
    assert client.get(url, headers=headers(staff_auth)).status_code == 200
    forbidden, _ = command(client, customer_auth, invoice, "CONFIRM")
    assert forbidden.status_code == 403
    confirmed, payload = command(client, staff_auth, invoice, "CONFIRM")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["state"] == "CONFIRMED"
    assert confirmed.json()["remaining"] == "1416.00"
    retry = client.post(f"{url}/commands", json=payload, headers=headers(staff_auth))
    assert retry.status_code == 200
    assert retry.json()["version"] == confirmed.json()["version"]
    customer = db.get(Customer, invoice.customer_id)
    customer.name = "Changed current profile"
    customer.billing_city = "Changed city"
    db.commit()
    own = client.get(url, headers=headers(customer_auth))
    assert own.status_code == 200
    assert own.json()["customer_name"] == "Subscription owner"
    assert "delivery_attempts" not in own.json()
    assert "history" not in own.json()
    assert "cancel_reason" not in own.json()
    other = Customer(name="Other account", email_normalized="invoice_other@brightloop.test")
    db.add(other)
    db.commit()
    alien = generate(db, admin_auth, {**draft_data, "customer_id": str(other.id)})
    command(client, admin_auth, alien, "CONFIRM")
    assert client.get(f"/api/v1/invoices/{alien.id}", headers=headers(customer_auth)).status_code == 404
    listing = client.get("/api/v1/invoices?overdue=true", headers=headers(customer_auth)).json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == str(invoice.id)


def test_draft_metadata_only_and_cancelled_period_not_rebilled(db, client, admin_auth, customer_auth, draft_data):
    invoice = generate(db, admin_auth, draft_data)
    url = f"/api/v1/invoices/{invoice.id}"
    response = client.patch(f"{url}/draft-metadata", headers=headers(admin_auth), json={
        "expected_version": invoice.version, "reason": "Correct billing contact", "customer_email": "invalid"})
    assert response.status_code == 422
    response = client.patch(f"{url}/draft-metadata", headers=headers(admin_auth), json={
        "expected_version": invoice.version, "reason": "Change money", "total": "1.00"})
    assert response.status_code == 422
    response = client.patch(f"{url}/draft-metadata", headers=headers(admin_auth), json={
        "expected_version": invoice.version, "reason": "Correct due date", "due_date": "2025-01-30"})
    assert response.status_code == 422
    response = client.patch(f"{url}/draft-metadata", headers=headers(admin_auth), json={
        "expected_version": invoice.version, "reason": "Correct billing contact", "customer_email": "corrected@brightloop.test"})
    assert response.status_code == 200, response.text
    assert response.json()["customer_email"] == "corrected@brightloop.test"
    cancelled, _ = command(client, admin_auth, invoice, "CANCEL", reason="Unaccepted invoice")
    assert cancelled.status_code == 200
    assert client.get(url, headers=headers(customer_auth)).status_code == 404
    replay = process_next_period(db, invoice.subscription_id, date(2025, 1, 31))
    db.commit()
    assert replay.state == "EXISTING"
    assert replay.invoice_id == invoice.id
    assert db.scalar(select(func.count()).select_from(Invoice)) == 1


def test_zero_total_confirmation_is_paid_without_fake_payment(db, client, admin_auth, customer_auth, draft_data):
    plan = db.get(Plan, uuid.UUID(draft_data["plan_id"]))
    plan.base_fee = Decimal("0.00")
    plan.extra_seat_unit_price = Decimal("0.00")
    db.commit()
    invoice = generate(db, admin_auth, draft_data)
    confirmed, _ = command(client, admin_auth, invoice, "CONFIRM")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["state"] == "PAID"
    assert confirmed.json()["remaining"] == "0.00"
    assert db.scalar(select(func.count()).select_from(Payment)) == 0
    assert client.get(f"/api/v1/invoices/{invoice.id}", headers=headers(customer_auth)).status_code == 200


def test_cancel_issued_invoice_remains_visible_but_not_payable(db, client, admin_auth, customer_auth, draft_data):
    invoice = generate(db, admin_auth, draft_data)
    confirmed, _ = command(client, admin_auth, invoice, "CONFIRM")
    assert confirmed.status_code == 200
    cancelled, _ = command(client, admin_auth, invoice, "CANCEL", reason="Customer requested cancellation")
    assert cancelled.status_code == 200, cancelled.text
    own = client.get(f"/api/v1/invoices/{invoice.id}", headers=headers(customer_auth)).json()
    assert own["state"] == "CANCELLED"
    assert own["remaining"] == "0.00"
    assert own["overdue"] is False
    assert client.get("/api/v1/invoices?overdue=true", headers=headers(customer_auth)).json()["total"] == 0
