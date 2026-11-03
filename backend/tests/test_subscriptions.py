"""PostgreSQL/API regressions for the quotation aggregate."""
from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from sqlalchemy import func, select

from app.core.datetime_utils import get_business_today
from app.models.catalog import Plan
from app.models.customers import Customer
from app.models.subscriptions import AgreementVersion, Subscription, SubscriptionTerm
from app.models.taxes import PlanTax, TaxRule


def headers(auth):
    return {"Authorization": f"Bearer {auth['token']}", "X-CSRF-Token": auth["csrf_token"],
            "Origin": "http://localhost:3000"}


@pytest.fixture
def draft_data(db, customer_auth):
    customer = Customer(name="Subscription owner", email_normalized="sub_owner@brightloop.test",
                        user_id=customer_auth["user"].id)
    plan = Plan(name="Subscription plan", base_fee=Decimal("1000.00"), minimum_seats=5,
                extra_seat_unit_price=Decimal("100.00"), interval="MONTHLY")
    tax = TaxRule(name="GST", classification="GST", rate=Decimal("18.00"))
    db.add_all([customer, plan, tax])
    db.flush()
    db.add(PlanTax(plan_id=plan.id, tax_rule_id=tax.id))
    db.commit()
    today = get_business_today()
    return {"customer_id": str(customer.id), "plan_id": str(plan.id), "seat_quantity": 7,
            "start_date": today.isoformat(), "expiry_date": (today + timedelta(days=365)).isoformat()}


def create(client, admin_auth, payload):
    response = client.post("/api/v1/subscriptions", json=payload, headers=headers(admin_auth))
    assert response.status_code == 201, response.text
    return response.json()


def command(client, auth, sub, action, **extra):
    payload = {"expected_version": sub["version"], "request_key": uuid.uuid4().hex, "action": action, **extra}
    response = client.post(f"/api/v1/subscriptions/{sub['id']}/commands", json=payload, headers=headers(auth))
    return response, payload


def test_quote_acceptance_snapshots_and_idempotency(client, db, admin_auth, customer_auth, draft_data):
    sub = create(client, admin_auth, draft_data)
    assert sub["state"] == "DRAFT"
    assert [line["unit_price"] for line in sub["agreements"][0]["lines"]] == ["1000.00", "100.00"]
    issued, _ = command(client, admin_auth, sub, "ISSUE")
    assert issued.status_code == 200, issued.text
    sub = issued.json()
    assert sub["agreements"][0]["valid_until"] == (get_business_today() + timedelta(days=30)).isoformat()
    plan = db.get(Plan, uuid.UUID(draft_data["plan_id"]))
    plan.base_fee = Decimal("9000.00")
    plan.allow_pause = False
    db.scalar(select(TaxRule).where(TaxRule.name == "GST")).rate = Decimal("5.00")
    db.commit()
    confirmed, payload = command(client, admin_auth, sub, "CONFIRM")
    assert confirmed.status_code == 200, confirmed.text
    sub = confirmed.json()
    assert sub["state"] == "CONFIRMED"
    assert sub["agreements"][0]["lines"][0]["unit_price"] == "1000.00"
    assert sub["agreements"][0]["lines"][0]["taxes"][0]["rate"] == "18.0000"
    assert sub["agreements"][0]["policies"]["allow_pause"] is True
    retry = client.post(f"/api/v1/subscriptions/{sub['id']}/commands", json=payload, headers=headers(admin_auth))
    assert retry.status_code == 200, retry.text
    assert retry.json()["version"] == sub["version"]
    assert db.scalar(select(func.count()).select_from(Subscription)) == 1
    assert db.scalar(select(func.count()).select_from(SubscriptionTerm)) == 1
    active, _ = command(client, admin_auth, sub, "ACTIVATE")
    assert active.status_code == 200, active.text
    assert active.json()["next_billing_date"] == draft_data["start_date"]
    own = client.get(f"/api/v1/subscriptions/{sub['id']}", headers=headers(customer_auth))
    assert own.status_code == 200
    assert "override_reason" not in own.json()["agreements"][0]["lines"][0]


def test_issued_revision_is_immutable(client, db, admin_auth, draft_data):
    sub = create(client, admin_auth, draft_data)
    issued, _ = command(client, admin_auth, sub, "ISSUE")
    sub = issued.json()
    old_id = sub["agreements"][0]["id"]
    updated = client.patch(f"/api/v1/subscriptions/{sub['id']}", headers=headers(admin_auth),
                           json={**draft_data, "seat_quantity": 8, "expected_version": sub["version"]})
    assert updated.status_code == 200, updated.text
    revised, _ = command(client, admin_auth, updated.json(), "ISSUE")
    assert revised.status_code == 200, revised.text
    assert revised.json()["agreements"][1]["state"] == "SUPERSEDED"
    historical = db.get(AgreementVersion, uuid.UUID(old_id))
    assert historical.seat_quantity == 7
    assert len(revised.json()["agreements"]) == 2
    stale, _ = command(client, admin_auth, sub, "CONFIRM")
    assert stale.status_code == 409


def test_invalid_transitions_dates_and_ownership(client, db, admin_auth, customer_auth, staff_auth, draft_data):
    sub = create(client, staff_auth, draft_data)
    invalid, _ = command(client, staff_auth, sub, "ACTIVATE")
    assert invalid.status_code == 409
    forbidden, _ = command(client, customer_auth, sub, "ISSUE")
    assert forbidden.status_code == 403
    other = Customer(name="Other", email_normalized="other_sub@brightloop.test")
    db.add(other)
    db.commit()
    alien = create(client, admin_auth, {**draft_data, "customer_id": str(other.id)})
    assert client.get(f"/api/v1/subscriptions/{alien['id']}", headers=headers(customer_auth)).status_code == 404
    listing = client.get("/api/v1/subscriptions", headers=headers(customer_auth)).json()
    assert listing["total"] == 1
    assert listing["items"][0]["id"] == sub["id"]
    bad = client.post("/api/v1/subscriptions", headers=headers(admin_auth), json={**draft_data, "seat_quantity": 1})
    assert bad.status_code == 422
    bad = client.post("/api/v1/subscriptions", headers=headers(admin_auth),
                      json={**draft_data, "expiry_date": draft_data["start_date"]})
    assert bad.status_code == 422


def test_expired_quote_requires_revision(client, db, admin_auth, draft_data):
    sub = create(client, admin_auth, draft_data)
    issued, _ = command(client, admin_auth, sub, "ISSUE")
    sub = issued.json()
    version = db.get(AgreementVersion, uuid.UUID(sub["agreements"][0]["id"]))
    version.valid_until = get_business_today() - timedelta(days=1)
    db.commit()
    response, _ = command(client, admin_auth, sub, "CONFIRM")
    assert response.status_code == 409
    assert "expired" in response.text


def test_atomic_save_and_issue_and_list_filters(client, admin_auth, draft_data):
    response = client.post("/api/v1/subscriptions?issue=true", json=draft_data, headers=headers(admin_auth))
    assert response.status_code == 201, response.text
    sub = response.json()
    assert sub["state"] == "QUOTATION"
    assert sub["agreements"][0]["state"] == "ISSUED"
    listing = client.get("/api/v1/subscriptions", params={"plan_id": draft_data["plan_id"],
                         "customer_id": draft_data["customer_id"], "expiry_before": draft_data["expiry_date"]},
                         headers=headers(admin_auth))
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["recurring_amount"] == "1416.00"
    assert listing.json()["items"][0]["request_count"] == 0
    assert client.get("/api/v1/subscriptions?pending_requests=true", headers=headers(admin_auth)).json()["total"] == 0


def test_draft_creation_key_replays_same_aggregate_and_rejects_changed_intent(db, client, admin_auth, draft_data):
    request_headers = {**headers(admin_auth), "Idempotency-Key": uuid.uuid4().hex}
    first = client.post("/api/v1/subscriptions?issue=true", json=draft_data, headers=request_headers)
    assert first.status_code == 201, first.text
    replay = client.post("/api/v1/subscriptions?issue=true", json=draft_data, headers=request_headers)
    assert replay.status_code == 201
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["version"] == first.json()["version"]
    conflict = client.post("/api/v1/subscriptions?issue=true", json={**draft_data, "seat_quantity": 8}, headers=request_headers)
    assert conflict.status_code == 409
    assert db.scalar(select(func.count()).select_from(Subscription)) == 1
