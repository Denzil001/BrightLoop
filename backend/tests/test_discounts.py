from datetime import date, timedelta
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient


def test_discount_rule_crud_revisions_and_deactivation(client: TestClient, admin_auth, staff_auth):
    """Admin can create discount rules, add revisions, and deactivate; Staff can read; validation enforced."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    today = date.today()
    next_year = today + timedelta(days=365)

    # 1. Create whole-subscription percent discount rule
    payload = {
        "name": "Annual Special 10%",
        "maximum_uses": 100,
        "initial_revision": {
            "type": "PERCENT",
            "amount": None,
            "rate": "10.0000",
            "minimum_purchase": "500.00",
            "minimum_quantity": 5,
            "scope": "SUBSCRIPTION",
            "valid_from": today.isoformat(),
            "valid_to": next_year.isoformat(),
            "product_ids": [],
        },
    }
    resp = client.post("/api/v1/discounts", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    rule_data = resp.json()
    rule_id = rule_data["id"]
    assert rule_data["name"] == "Annual Special 10%"
    assert rule_data["maximum_uses"] == 100
    assert len(rule_data["revisions"]) == 1
    assert rule_data["revisions"][0]["revision"] == 1
    assert rule_data["revisions"][0]["rate"] == "10.0000"

    # 2. Add Revision 2 (bump to 15%)
    rev2_payload = {
        "type": "PERCENT",
        "rate": "15.0000",
        "scope": "SUBSCRIPTION",
        "valid_from": today.isoformat(),
        "valid_to": next_year.isoformat(),
        "product_ids": [],
    }
    rev2_resp = client.post(f"/api/v1/discounts/{rule_id}/revisions", json=rev2_payload, headers=admin_headers)
    assert rev2_resp.status_code == 201, rev2_resp.text
    rule_data2 = rev2_resp.json()
    assert len(rule_data2["revisions"]) == 2
    assert rule_data2["version"] == 2
    assert rule_data2["revisions"][0]["revision"] == 2
    assert rule_data2["revisions"][0]["rate"] == "15.0000"

    # 3. Staff can read discount rules
    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}"}
    staff_resp = client.get(f"/api/v1/discounts/{rule_id}", headers=staff_headers)
    assert staff_resp.status_code == 200
    assert staff_resp.json()["name"] == "Annual Special 10%"

    # 4. Deactivate discount rule
    deact_resp = client.post(
        f"/api/v1/discounts/{rule_id}/deactivate",
        json={"disabled_from": today.isoformat(), "reason": "Campaign ended"},
        headers=admin_headers,
    )
    assert deact_resp.status_code == 200
    assert deact_resp.json()["disabled_from"] == today.isoformat()


def test_discount_prospective_deactivation_rules(client: TestClient, admin_auth):
    """Discount deactivation cannot be backdated, and an already effective cutoff date cannot be rewritten."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=7)

    rule = client.post(
        "/api/v1/discounts",
        json={
            "name": "Deactivation Test Rule",
            "initial_revision": {
                "type": "PERCENT",
                "rate": "10.0000",
                "scope": "SUBSCRIPTION",
                "valid_from": today.isoformat(),
                "valid_to": next_week.isoformat(),
            },
        },
        headers=admin_headers,
    ).json()
    rule_id = rule["id"]

    # 1. Backdated deactivation (yesterday) -> rejected with 400
    backdated_resp = client.post(
        f"/api/v1/discounts/{rule_id}/deactivate",
        json={"disabled_from": yesterday.isoformat()},
        headers=admin_headers,
    )
    assert backdated_resp.status_code == 422
    err_msg = backdated_resp.json().get("detail") or backdated_resp.json().get("error", {}).get("message")
    assert "cannot be backdated" in err_msg

    # 2. Prospective deactivation (today) -> accepted
    deact_today = client.post(
        f"/api/v1/discounts/{rule_id}/deactivate",
        json={"disabled_from": today.isoformat()},
        headers=admin_headers,
    )
    assert deact_today.status_code == 200
    assert deact_today.json()["disabled_from"] == today.isoformat()

    # 3. Rewriting an already effective historical cutoff date -> rejected with 400
    rewrite_resp = client.post(
        f"/api/v1/discounts/{rule_id}/deactivate",
        json={"disabled_from": tomorrow.isoformat()},
        headers=admin_headers,
    )
    assert rewrite_resp.status_code == 409
    err_rewrite = rewrite_resp.json().get("detail") or rewrite_resp.json().get("error", {}).get("message")
    assert "Cannot modify an already effective historical cutoff" in err_rewrite



def test_discount_validation_rules(client: TestClient, admin_auth):
    """Validation: FIXED requires amount, PERCENT requires rate; PRODUCT requires product_ids; invalid dates rejected."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    today = date.today()
    yesterday = today - timedelta(days=1)

    # 1. FIXED without amount -> rejected
    bad_fixed = {
        "name": "Bad Fixed",
        "initial_revision": {
            "type": "FIXED",
            "amount": None,
            "rate": None,
            "scope": "SUBSCRIPTION",
            "valid_from": today.isoformat(),
            "valid_to": today.isoformat(),
        },
    }
    assert client.post("/api/v1/discounts", json=bad_fixed, headers=admin_headers).status_code == 422

    # 2. PRODUCT scope without products -> rejected
    bad_prod = {
        "name": "Bad Product Discount",
        "initial_revision": {
            "type": "PERCENT",
            "rate": "20.0000",
            "scope": "PRODUCT",
            "valid_from": today.isoformat(),
            "valid_to": today.isoformat(),
            "product_ids": [],
        },
    }
    assert client.post("/api/v1/discounts", json=bad_prod, headers=admin_headers).status_code == 422

    # 3. valid_to < valid_from -> rejected
    bad_dates = {
        "name": "Bad Dates",
        "initial_revision": {
            "type": "PERCENT",
            "rate": "10.0000",
            "scope": "SUBSCRIPTION",
            "valid_from": today.isoformat(),
            "valid_to": yesterday.isoformat(),
        },
    }
    assert client.post("/api/v1/discounts", json=bad_dates, headers=admin_headers).status_code == 422


def test_active_filter_and_current_revision_use_business_date(db, client, admin_auth, monkeypatch):
    from datetime import date
    from app.api.v1.endpoints import discounts
    from app.models.discounts import DiscountRule
    cutoff = date(2030, 1, 2)
    rule = DiscountRule(name="Business date cutoff", disabled_from=cutoff)
    db.add(rule)
    db.commit()
    monkeypatch.setattr(discounts, "get_business_today", lambda: cutoff)
    from test_subscriptions import headers
    active = client.get("/api/v1/discounts?active=true&search=Business%20date%20cutoff", headers=headers(admin_auth))
    inactive = client.get("/api/v1/discounts?active=false&search=Business%20date%20cutoff", headers=headers(admin_auth))
    assert active.status_code == inactive.status_code == 200
    assert active.json()["total"] == 0
    assert inactive.json()["items"][0]["id"] == str(rule.id)
