"""Dated event, request review and calendar regressions."""
from datetime import date, timedelta
from decimal import Decimal
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.datetime_utils import get_business_today
from app.models.subscriptions import Subscription, SubscriptionEvent, SubscriptionPause, SubscriptionTerm
from app.services.calendar import boundary, is_boundary
from app.services.lifecycle import apply_event
from test_subscriptions import command, create, draft_data, headers


@pytest.mark.parametrize("anchor,interval,offset,expected", [
    (date(2025, 1, 31), "MONTHLY", 1, date(2025, 2, 28)),
    (date(2025, 1, 31), "MONTHLY", 2, date(2025, 3, 31)),
    (date(2024, 2, 29), "YEARLY", 1, date(2025, 2, 28)),
    (date(2024, 2, 29), "YEARLY", 4, date(2028, 2, 29)),
    (date(2026, 1, 30), "WEEKLY", 2, date(2026, 2, 13)),
])
def test_calendar_restores_anchor(anchor, interval, offset, expected):
    assert boundary(anchor, interval, offset) == expected
    assert is_boundary(anchor, interval, expected)


def activate(client, admin_auth, draft_data):
    sub = create(client, admin_auth, draft_data)
    for action in ("ISSUE", "CONFIRM", "ACTIVATE"):
        response, _ = command(client, admin_auth, sub, action)
        assert response.status_code == 200, response.text
        sub = response.json()
    return sub


def test_request_approval_schedules_then_pause_resume_extends(db, client, admin_auth, customer_auth, draft_data):
    sub = activate(client, admin_auth, draft_data)
    term = db.scalar(select(SubscriptionTerm))
    pause_date = boundary(term.start_date, term.interval, 1)
    payload = {"action": "PAUSE", "effective_date": pause_date.isoformat(),
               "reason": "Travelling", "expected_version": sub["version"]}
    url = f"/api/v1/subscriptions/{sub['id']}"
    submitted = client.post(f"{url}/requests", json=payload, headers=headers(customer_auth))
    assert submitted.status_code == 201, submitted.text
    sub = submitted.json()
    assert sub["state"] == "ACTIVE"
    request_id = sub["requests"][0]["id"]
    review = {"decision": "APPROVE", "reason": "Approved for next boundary",
              "expected_version": sub["version"], "request_key": uuid.uuid4().hex}
    denied = client.post(f"{url}/requests/{request_id}/review", json=review, headers=headers(customer_auth))
    assert denied.status_code == 403
    approved = client.post(f"{url}/requests/{request_id}/review", json=review, headers=headers(admin_auth))
    assert approved.status_code == 200, approved.text
    assert approved.json()["state"] == "ACTIVE"
    assert approved.json()["requests"][0]["status"] == "APPROVED"
    customer_view = client.get(url, headers=headers(customer_auth)).json()["requests"][0]
    assert customer_view["reviewer_name"]
    assert customer_view["reviewed_at"]
    assert "reviewer_id" not in customer_view
    retry = client.post(f"{url}/requests/{request_id}/review", json=review, headers=headers(admin_auth))
    assert retry.status_code == 200
    event = db.scalar(select(SubscriptionEvent).where(SubscriptionEvent.action == "PAUSE"))
    subscription = db.get(Subscription, uuid.UUID(sub["id"]))
    with pytest.raises(HTTPException):
        apply_event(db, subscription, event)
    apply_event(db, subscription, event, as_of=pause_date)
    db.commit()
    assert subscription.state == "PAUSED"
    original_expiry = term.expiry_date
    resume_date = pause_date + timedelta(days=10)
    resume = client.post(f"{url}/lifecycle", headers=headers(admin_auth), json={
        "action": "RESUME", "effective_date": resume_date.isoformat(), "reason": "Returned",
        "expected_version": subscription.version, "request_key": uuid.uuid4().hex})
    assert resume.status_code == 200, resume.text
    resume_event = db.scalar(select(SubscriptionEvent).where(SubscriptionEvent.action == "RESUME"))
    apply_event(db, subscription, resume_event, as_of=resume_date)
    db.commit()
    assert subscription.state == "ACTIVE"
    assert term.expiry_date == original_expiry + timedelta(days=10)
    assert term.original_anchor_date == resume_date
    assert db.scalar(select(SubscriptionPause)).resumed_date == resume_date
    apply_event(db, subscription, resume_event, as_of=resume_date)
    assert term.expiry_date == original_expiry + timedelta(days=10)


def test_cancel_request_staleness_and_policy_guards(db, client, admin_auth, customer_auth, draft_data):
    sub = activate(client, admin_auth, draft_data)
    term = db.scalar(select(SubscriptionTerm))
    url = f"/api/v1/subscriptions/{sub['id']}"
    payload = {"action": "PAUSE", "effective_date": boundary(term.start_date, term.interval, 1).isoformat(),
               "reason": "Pause service", "expected_version": sub["version"]}
    response = client.post(f"{url}/requests", json=payload, headers=headers(customer_auth))
    assert response.status_code == 201, response.text
    request_id = response.json()["requests"][0]["id"]
    assert client.post(f"{url}/requests", json=payload, headers=headers(customer_auth)).status_code == 409
    cancelled = client.post(f"{url}/requests/{request_id}/cancel", headers=headers(customer_auth))
    assert cancelled.status_code == 200
    assert cancelled.json()["requests"][0]["status"] == "CANCELLED"
    assert client.post(f"{url}/requests/{request_id}/cancel", headers=headers(customer_auth)).status_code == 409
    term.allow_pause = False
    db.commit()
    assert client.post(f"{url}/requests", json=payload, headers=headers(customer_auth)).status_code == 409
    term.allow_pause = True
    db.commit()
    submitted = client.post(f"{url}/requests", json=payload, headers=headers(customer_auth))
    assert submitted.status_code == 201
    request_id = next(item["id"] for item in submitted.json()["requests"] if item["status"] == "PENDING")
    subscription = db.get(Subscription, uuid.UUID(sub["id"]))
    subscription.version += 1
    db.commit()
    review = {"decision": "APPROVE", "reason": "Approve", "expected_version": subscription.version,
              "request_key": uuid.uuid4().hex}
    assert client.post(f"{url}/requests/{request_id}/review", json=review, headers=headers(admin_auth)).status_code == 409
    review.update(decision="REJECT", reason="Terms changed; review the current service dates.")
    rejected = client.post(f"{url}/requests/{request_id}/review", json=review, headers=headers(admin_auth))
    assert rejected.status_code == 200, rejected.text
    assert next(item for item in rejected.json()["requests"] if item["id"] == request_id)["status"] == "REJECTED"


def test_due_or_non_boundary_changes_rejected(client, admin_auth, draft_data):
    sub = activate(client, admin_auth, draft_data)
    for effective in (get_business_today(), get_business_today() + timedelta(days=1)):
        response = client.post(f"/api/v1/subscriptions/{sub['id']}/lifecycle", headers=headers(admin_auth), json={
            "action": "PAUSE", "effective_date": effective.isoformat(), "reason": "Pause",
            "expected_version": sub["version"], "request_key": uuid.uuid4().hex})
        assert response.status_code == 422, response.text


def test_addon_and_renewal_create_new_accepted_versions(db, client, admin_auth, draft_data):
    sub = activate(client, admin_auth, draft_data)
    subscription = db.get(Subscription, uuid.UUID(sub["id"]))
    term = db.scalar(select(SubscriptionTerm))
    effective = boundary(term.start_date, term.interval, 1)
    proposal = {**draft_data, "start_date": effective.isoformat(), "seat_quantity": 9, "lines": []}
    response = client.post(f"/api/v1/subscriptions/{sub['id']}/lifecycle", headers=headers(admin_auth), json={
        "action": "ADDON_CHANGE", "effective_date": effective.isoformat(), "reason": "Two extra seats agreed",
        "proposal": proposal, "expected_version": sub["version"], "request_key": uuid.uuid4().hex})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["seat_quantity"] == 7  # future agreement has not changed today's service
    assert result["agreements"][0]["seat_quantity"] == 9
    assert result["agreements"][1]["seat_quantity"] == 7
    event = db.scalar(select(SubscriptionEvent).where(SubscriptionEvent.action == "ADDON_CHANGE"))
    apply_event(db, subscription, event, as_of=effective)
    db.commit()
    assert subscription.seat_quantity == 9
    expiry = term.expiry_date
    proposal.update(start_date=expiry.isoformat(), expiry_date=(expiry + timedelta(days=365)).isoformat())
    renewal = client.post(f"/api/v1/subscriptions/{sub['id']}/lifecycle", headers=headers(admin_auth), json={
        "action": "RENEW", "effective_date": expiry.isoformat(), "reason": "Renewed annual service term",
        "proposal": proposal, "expected_version": subscription.version, "request_key": uuid.uuid4().hex})
    assert renewal.status_code == 200, renewal.text
    event = db.scalar(select(SubscriptionEvent).where(SubscriptionEvent.action == "RENEW"))
    apply_event(db, subscription, event, as_of=expiry)
    db.commit()
    terms = db.scalars(select(SubscriptionTerm).order_by(SubscriptionTerm.sequence)).all()
    assert len(terms) == 2
    assert terms[0].expiry_date == terms[1].start_date
    assert subscription.next_billing_date == expiry
    assert subscription.state == "ACTIVE"


def test_customer_change_options_exclude_internal_fields(db, client, admin_auth, customer_auth, draft_data):
    from app.models.catalog import Product
    product = Product(name="Public add-on", type="ADDON", sales_price=20, cost_price=7, notes="Internal vendor note")
    db.add(product)
    db.commit()
    sub = activate(client, admin_auth, draft_data)
    response = client.get(f"/api/v1/subscriptions/{sub['id']}/change-options", headers=headers(customer_auth))
    assert response.status_code == 200, response.text
    assert response.json()["products"][0]["sales_price"] == "20.00"
    plan_options = response.json()["plans"][0]
    assert plan_options["allow_pause"] == sub["terms"][0]["policies"]["allow_pause"]
    assert all(isinstance(plan_options[key], bool) for key in (
        "allow_pause", "allow_resume", "allow_renewal", "allow_early_closure", "auto_close_on_expiry"))
    assert "cost_price" not in response.text
    assert "Internal vendor note" not in response.text
    assert "notes" not in response.text
    db.add_all([Product(name=f"A choice {index:03d}", type="ADDON", sales_price=1, cost_price=0) for index in range(105)])
    db.commit()
    first_page = client.get(f"/api/v1/subscriptions/{sub['id']}/change-options", headers=headers(customer_auth)).json()
    assert len(first_page["products"]) == 100
    assert str(product.id) not in {item["id"] for item in first_page["products"]}
    selected = client.get(f"/api/v1/subscriptions/{sub['id']}/change-options",
                          params={"product_id": str(product.id), "search": "no match"}, headers=headers(customer_auth))
    assert [item["id"] for item in selected.json()["products"]] == [str(product.id)]
    assert "cost_price" not in selected.text and "notes" not in selected.text
    assert client.get(f"/api/v1/subscriptions/{uuid.uuid4()}/change-options",
                      params={"product_id": str(product.id)}, headers=headers(customer_auth)).status_code == 404
    assert client.get(f"/api/v1/subscriptions/{sub['id']}/change-options",
                      params={"product_id": "invalid"}, headers=headers(customer_auth)).status_code == 422


def test_addon_keeps_current_term_policy_and_exposes_frozen_line_estimate(db, client, admin_auth, customer_auth, draft_data):
    from app.models.catalog import Plan
    sub = activate(client, admin_auth, draft_data)
    term = db.scalar(select(SubscriptionTerm))
    plan = db.get(Plan, uuid.UUID(draft_data["plan_id"]))
    original = sub["terms"][0]["policies"]
    plan.allow_pause = not term.allow_pause
    plan.allow_renewal = not term.allow_renewal
    db.commit()
    effective = boundary(term.start_date, term.interval, 1)
    proposal = {**draft_data, "start_date": effective.isoformat(), "seat_quantity": 9, "lines": []}
    response = client.post(f"/api/v1/subscriptions/{sub['id']}/lifecycle", headers=headers(admin_auth), json={
        "action": "ADDON_CHANGE", "effective_date": effective.isoformat(), "reason": "Extra seats only",
        "proposal": proposal, "expected_version": sub["version"], "request_key": uuid.uuid4().hex})
    assert response.status_code == 200, response.text
    result = client.get(f"/api/v1/subscriptions/{sub['id']}", headers=headers(customer_auth)).json()
    assert result["terms"][0]["policies"] == original
    assert result["agreements"][0]["policies"] == original
    assert result["agreements"][0]["pending_change"] is True
    assert result["agreements"][1]["pending_change"] is False
    lines = result["agreements"][0]["lines"]
    assert all(isinstance(line["total"], str) and isinstance(line["tax_amount"], str) for line in lines)
    assert sum(Decimal(line["total"]) for line in lines) == Decimal(result["agreements"][0]["pricing_estimate"]["total"])


def test_request_review_rejects_changed_commercial_terms(db, client, admin_auth, customer_auth, draft_data):
    from app.models.catalog import Plan
    sub = activate(client, admin_auth, draft_data)
    term = db.scalar(select(SubscriptionTerm))
    effective = boundary(term.start_date, term.interval, 1)
    url = f"/api/v1/subscriptions/{sub['id']}"
    submitted = client.post(f"{url}/requests", headers=headers(customer_auth), json={
        "action": "ADDON_CHANGE", "effective_date": effective.isoformat(), "reason": "Please change my seats",
        "expected_version": sub["version"], "proposal": {**draft_data, "seat_quantity": 8,
            "start_date": effective.isoformat(), "lines": []}})
    assert submitted.status_code == 201, submitted.text
    request_id = submitted.json()["requests"][0]["id"]
    plan = db.get(Plan, uuid.UUID(draft_data["plan_id"]))
    plan.base_fee = Decimal("2000.00")
    db.commit()
    reviewed = client.post(f"{url}/requests/{request_id}/review", headers=headers(admin_auth), json={
        "decision": "APPROVE", "reason": "Approved", "expected_version": sub["version"], "request_key": uuid.uuid4().hex})
    assert reviewed.status_code == 409, reviewed.text
    assert "Pricing changed" in reviewed.text
    after = client.get(url, headers=headers(customer_auth)).json()
    assert after["requests"][0]["status"] == "PENDING"
    assert len(after["agreements"]) == 1
