from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import select

from app.core.datetime_utils import get_business_today
from app.models.catalog import Plan
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.subscriptions import Subscription
from app.services.billing import process_next_period
from test_billing import contract
from test_invoices import command
from test_payments import payload
from test_subscriptions import create, draft_data, headers


@pytest.fixture
def report_case(db, client, admin_auth, customer_auth, draft_data):
    today = get_business_today()
    start = today - timedelta(days=40)
    sub = contract(db, admin_auth["user"], draft_data, start_date=start.isoformat(), expiry_date=(today + timedelta(days=365)).isoformat())
    first = process_next_period(db, sub.id, start)
    db.commit()
    invoice = db.get(Invoice, first.invoice_id)
    assert command(client, admin_auth, invoice, "CONFIRM")[0].status_code == 200
    payment = client.post(f"/api/v1/invoices/{invoice.id}/payments", headers=headers(admin_auth),
        json=payload(payment_date=(today - timedelta(days=2)).isoformat()))
    assert payment.status_code == 201, payment.text
    process_next_period(db, sub.id, today)  # next draft must not enter receivables
    db.commit()
    other = Customer(name="Report other account", email_normalized="report_other@brightloop.test")
    plan = Plan(name="Report other plan", base_fee=Decimal("500.00"), minimum_seats=1,
                extra_seat_unit_price=Decimal("0.00"), interval="MONTHLY")
    db.add_all([other, plan]); db.commit()
    other_sub = contract(db, admin_auth["user"], {**draft_data, "customer_id": str(other.id), "plan_id": str(plan.id), "seat_quantity": 1},
                         start_date=(today - timedelta(days=30)).isoformat(), expiry_date=(today + timedelta(days=10)).isoformat())
    result = process_next_period(db, other_sub.id, today); db.commit()
    other_invoice = db.get(Invoice, result.invoice_id)
    assert command(client, admin_auth, other_invoice, "CONFIRM")[0].status_code == 200
    expired = contract(db, admin_auth["user"], draft_data)  # 2025 service, still ACTIVE cache
    paused = contract(db, admin_auth["user"], draft_data, start_date=today.isoformat(), expiry_date=(today + timedelta(days=90)).isoformat())
    paused.state = "PAUSED"; db.commit()
    quote = create(client, admin_auth, draft_data)
    from test_subscriptions import command as sub_command
    assert sub_command(client, admin_auth, quote, "ISSUE")[0].status_code == 200
    from app.services.calendar import boundary
    offset = 1
    while (requested := boundary(start, "MONTHLY", offset)) <= today:
        offset += 1
    request = client.post(f"/api/v1/subscriptions/{sub.id}/requests", headers=headers(customer_auth), json={
        "action": "PAUSE", "effective_date": requested.isoformat(), "reason": "Upcoming leave", "expected_version": sub.version})
    assert request.status_code == 201, request.text
    return {"invoice_id": invoice.id, "other_invoice_id": other_invoice.id, "other_plan_id": plan.id,
            "customer_id": sub.customer_id, "sub_id": sub.id, "other_sub_id": other_sub.id, "today": today}


def test_finance_summary_and_detail_views_reconcile(client, admin_auth, report_case):
    today = report_case["today"]
    params = {"date_from": (today - timedelta(days=2)).isoformat(), "date_to": today.isoformat()}
    response = client.get("/api/v1/reports/summary", params=params, headers=headers(admin_auth))
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["received"] == "1000.00" and summary["receipt_count"] == 1
    assert summary["outstanding"] == "916.00" and summary["outstanding_count"] == 2
    assert summary["overdue"] == "416.00" and summary["overdue_count"] == 1
    assert summary["active_subscriptions"] == 2
    for view, field, expected in [("receipts", "amount", "1000.00"), ("outstanding", "remaining", "916.00"), ("overdue", "remaining", "416.00")]:
        detail = client.get("/api/v1/reports/details", params={**params, "view": view}, headers=headers(admin_auth))
        assert detail.status_code == 200, detail.text
        assert sum(Decimal(row[field]) for row in detail.json()["items"]) == Decimal(expected)
    active = client.get("/api/v1/reports/details?view=active&page_size=1", headers=headers(admin_auth)).json()
    assert active["total"] == 2 and len(active["items"]) == 1
    assert summary["query_time_ms"] >= 0


def test_range_receipts_do_not_change_current_balances_and_filters_match(client, admin_auth, report_case):
    today = report_case["today"]
    base = {"date_from": today.isoformat(), "date_to": today.isoformat()}
    current = client.get("/api/v1/reports/summary", params=base, headers=headers(admin_auth)).json()
    assert current["received"] == "0.00" and current["outstanding"] == "916.00"
    own = client.get("/api/v1/reports/summary", params={**base, "customer_id": str(report_case["customer_id"])}, headers=headers(admin_auth)).json()
    assert own["outstanding"] == "416.00" and own["active_subscriptions"] == 1
    other = client.get("/api/v1/reports/summary", params={**base, "plan_id": str(report_case["other_plan_id"])}, headers=headers(admin_auth)).json()
    assert other["outstanding"] == "500.00" and other["overdue"] == "0.00"
    details = client.get("/api/v1/reports/details", params={"view": "outstanding", "plan_id": str(report_case["other_plan_id"])}, headers=headers(admin_auth)).json()
    assert details["total"] == 1 and details["items"][0]["id"] == str(report_case["other_invoice_id"])


def test_dashboard_roles_ownership_and_report_denials(client, admin_auth, staff_auth, customer_auth, report_case):
    for auth in (staff_auth, customer_auth):
        assert client.get("/api/v1/reports/summary", headers=headers(auth)).status_code == 403
        assert client.get("/api/v1/reports/details", headers=headers(auth)).status_code == 403
    own = client.get("/api/v1/dashboard", headers=headers(customer_auth))
    assert own.status_code == 200, own.text
    own = own.json()
    assert own["metrics"]["outstanding"] == "416.00"
    assert own["metrics"]["active_subscriptions"] == 1
    assert own["pending_request_count"] == 1
    assert all(invoice["id"] != str(report_case["other_invoice_id"]) for invoice in own["recent_invoices"])
    assert all(sub["id"] != str(report_case["other_sub_id"]) for sub in own["ending_subscriptions"])
    staff = client.get("/api/v1/dashboard", headers=headers(staff_auth))
    assert staff.status_code == 200, staff.text
    staff = staff.json()
    assert staff["quote_count"] == 1 and staff["pending_request_count"] == 1
    assert staff["invoice_action_count"] == 1 and staff["overdue_count"] == 1
    assert "metrics" not in staff and "received" not in staff and "outstanding" not in staff


def test_report_validation(client, admin_auth):
    assert client.get("/api/v1/reports/details?view=sql", headers=headers(admin_auth)).status_code == 422
    assert client.get("/api/v1/reports/summary?date_from=2026-11-02&date_to=2026-11-01", headers=headers(admin_auth)).status_code == 422


def test_due_approved_stop_is_not_counted_as_active_service(db, client, admin_auth, customer_auth, report_case):
    from app.models.subscriptions import SubscriptionEvent
    db.add(SubscriptionEvent(subscription_id=report_case["sub_id"], action="PAUSE", effective_date=report_case["today"], actor_id=admin_auth["user"].id))
    db.commit()
    summary = client.get("/api/v1/reports/summary", headers=headers(admin_auth)).json()
    assert summary["active_subscriptions"] == 1
    own = client.get("/api/v1/dashboard", headers=headers(customer_auth)).json()
    assert own["metrics"]["active_subscriptions"] == 0
    listing = client.get("/api/v1/subscriptions?service_active=true", headers=headers(customer_auth)).json()
    assert listing["total"] == 0


def test_reporting_preserves_financial_audit_records(db, client, admin_auth, report_case):
    from app.models.audit import AuditEvent
    from sqlalchemy import func
    before = db.scalar(select(func.count()).select_from(AuditEvent))
    actions = set(db.scalars(select(AuditEvent.action)))
    assert {"INVOICE_GENERATED", "INVOICE_CONFIRM", "PAYMENT_RECORDED"} <= actions
    for endpoint in ("/api/v1/reports/summary", "/api/v1/reports/details", "/api/v1/dashboard"):
        assert client.get(endpoint, headers=headers(admin_auth)).status_code == 200
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == before
