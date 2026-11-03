from datetime import date, timedelta
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient


def test_pricing_worked_acceptance_case_2888_64(client: TestClient, admin_auth, staff_auth):
    """
    Team-accepted worked case from docs/business-rules.md:
    - Base 1,000 includes 5 seats
    - 7 seats requested at excess 100/seat (2 excess seats = 200)
    - Add-on 2 x (base 200 + variant 560 = 760 -> 1,520)
    - Whole 10% discount
    - 18% tax on all paid lines
    Expected:
    Subtotal: 2,720.00
    Discount: 272.00
    Taxable: 2,448.00
    Tax: 440.64
    Total: 2,888.64
    """
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    today = date.today()
    next_year = today + timedelta(days=365)

    # 1. 18% Tax Rule
    tax_resp = client.post(
        "/api/v1/taxes",
        json={"name": "GST 18%", "classification": "GST", "rate": "18.0000", "active": True},
        headers=admin_headers,
    )
    assert tax_resp.status_code == 201
    tax_id = tax_resp.json()["id"]

    # 2. Base Product 200.00 + Variant 560.00 with 18% tax
    prod_resp = client.post(
        "/api/v1/products",
        json={
            "name": "Cloud Server Instance",
            "type": "SERVER",
            "sales_price": "200.00",
            "cost_price": "80.00",
            "tax_rule_ids": [tax_id],
        },
        headers=admin_headers,
    )
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    var_resp = client.post(
        f"/api/v1/products/{prod_id}/variants",
        json={"name": "High Memory 560", "price_adjustment": "560.00", "active": True},
        headers=admin_headers,
    )
    assert var_resp.status_code == 201
    var_id = var_resp.json()["id"]

    # 3. Plan: 1,000 base fee, 5 minimum seats, 100 extra seat price, with 18% tax
    plan_resp = client.post(
        "/api/v1/plans",
        json={
            "name": "Standard Enterprise Plan",
            "base_fee": "1000.00",
            "minimum_seats": 5,
            "extra_seat_unit_price": "100.00",
            "interval": "MONTHLY",
            "tax_rule_ids": [tax_id],
        },
        headers=admin_headers,
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["id"]

    # 4. Whole-subscription 10% discount rule
    disc_resp = client.post(
        "/api/v1/discounts",
        json={
            "name": "Whole 10% Discount",
            "initial_revision": {
                "type": "PERCENT",
                "rate": "10.0000",
                "scope": "SUBSCRIPTION",
                "valid_from": today.isoformat(),
                "valid_to": next_year.isoformat(),
                "product_ids": [],
            },
        },
        headers=admin_headers,
    )
    assert disc_resp.status_code == 201
    disc_id = disc_resp.json()["id"]

    # 5. Preview pricing via Staff user
    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}", "X-CSRF-Token": staff_auth["csrf_token"], "Origin": "http://localhost:3000"}
    preview_req = {
        "plan_id": plan_id,
        "seat_quantity": 7,
        "lines": [
            {
                "product_id": prod_id,
                "variant_id": var_id,
                "quantity": 2,
                "line_kind": "ADDON",
            }
        ],
        "discount_id": disc_id,
        "as_of_date": today.isoformat(),
    }
    preview_resp = client.post("/api/v1/pricing/preview", json=preview_req, headers=staff_headers)
    assert preview_resp.status_code == 200, preview_resp.text
    res = preview_resp.json()

    # Assert exact acceptance values
    assert res["subtotal"] == "2720.00"
    assert res["total_discount"] == "272.00"
    assert res["taxable_amount"] == "2448.00"
    assert res["total_tax"] == "440.64"
    assert res["total"] == "2888.64"

    # Line breakdown assertions
    lines = res["lines"]
    assert len(lines) == 3
    # Plan Base Line: 1000 subtotal, 100 discount, 900 discounted, 162 tax (18% of 900), 1062 total
    base_line = lines[0]
    assert base_line["line_kind"] == "PLAN_FEE"
    assert base_line["subtotal"] == "1000.00"
    assert base_line["discount_amount"] == "100.00"
    assert base_line["tax_amount"] == "162.00"

    # Excess Seats Line: 2 seats * 100 = 200 subtotal, 20 discount, 180 discounted, 32.40 tax, 212.40 total
    excess_line = lines[1]
    assert excess_line["line_kind"] == "EXCESS_SEATS"
    assert excess_line["quantity"] == 2
    assert excess_line["subtotal"] == "200.00"
    assert excess_line["discount_amount"] == "20.00"
    assert excess_line["tax_amount"] == "32.40"

    # Add-on Line: 2 * 760 = 1520 subtotal, 152 discount, 1368 discounted, 246.24 tax, 1614.24 total
    addon_line = lines[2]
    assert addon_line["line_kind"] == "ADDON"
    assert addon_line["quantity"] == 2
    assert addon_line["unit_price"] == "760.00"
    assert addon_line["subtotal"] == "1520.00"
    assert addon_line["discount_amount"] == "152.00"
    assert addon_line["tax_amount"] == "246.24"


def test_included_items_zero_charge_no_double_charging(client: TestClient, admin_auth, staff_auth):
    """Included items have 0 unit price, 0 subtotal, and do not increase invoice total."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    prod_resp = client.post(
        "/api/v1/products",
        json={"name": "Complimentary Backup", "type": "STORAGE", "sales_price": "50.00", "cost_price": "10.00"},
        headers=admin_headers,
    )
    prod_id = prod_resp.json()["id"]

    plan_resp = client.post(
        "/api/v1/plans",
        json={
            "name": "Simple Plan",
            "base_fee": "300.00",
            "minimum_seats": 1,
            "extra_seat_unit_price": "0.00",
            "interval": "MONTHLY",
            "items": [
                {
                    "ordinal": 1,
                    "product_id": prod_id,
                    "variant_id": None,
                    "included_quantity": 5,
                }
            ],
        },
        headers=admin_headers,
    )
    plan_id = plan_resp.json()["id"]

    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}", "X-CSRF-Token": staff_auth["csrf_token"], "Origin": "http://localhost:3000"}
    req = {
        "plan_id": plan_id,
        "seat_quantity": 1,
        "lines": [
            {
                "product_id": prod_id,
                "variant_id": None,
                "quantity": 5,
                "line_kind": "INCLUDED",
            }
        ],
    }
    resp = client.post("/api/v1/pricing/preview", json=req, headers=staff_headers)
    assert resp.status_code == 200
    res = resp.json()
    assert res["subtotal"] == "300.00"
    assert res["total"] == "300.00"

    # Check the included line
    inc_line = next(l for l in res["lines"] if l["line_kind"] == "INCLUDED")
    assert inc_line["unit_price"] == "0.00"
    assert inc_line["subtotal"] == "0.00"
    assert inc_line["discount_amount"] == "0.00"
    assert inc_line["tax_amount"] == "0.00"
    assert inc_line["total"] == "0.00"


def test_fixed_discount_minor_unit_proportional_allocation(client: TestClient, admin_auth, staff_auth):
    """
    Fixed discount of 10.00 allocated across 3 equal lines of 33.33, 33.33, 33.34:
    Proportional integer minor-unit allocation guarantees sum of discounts is exactly 10.00.
    """
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    today = date.today()
    next_year = today + timedelta(days=365)

    prod1 = client.post("/api/v1/products", json={"name": "P1", "type": "T", "sales_price": "33.33", "cost_price": "0.00"}, headers=admin_headers).json()["id"]
    prod2 = client.post("/api/v1/products", json={"name": "P2", "type": "T", "sales_price": "33.33", "cost_price": "0.00"}, headers=admin_headers).json()["id"]

    plan = client.post(
        "/api/v1/plans",
        json={"name": "P33 Plan", "base_fee": "33.34", "minimum_seats": 1, "extra_seat_unit_price": "0.00", "interval": "MONTHLY"},
        headers=admin_headers,
    ).json()["id"]

    disc = client.post(
        "/api/v1/discounts",
        json={
            "name": "Fixed $10 Off",
            "initial_revision": {
                "type": "FIXED",
                "amount": "10.00",
                "scope": "SUBSCRIPTION",
                "valid_from": today.isoformat(),
                "valid_to": next_year.isoformat(),
                "product_ids": [],
            },
        },
        headers=admin_headers,
    ).json()["id"]

    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}", "X-CSRF-Token": staff_auth["csrf_token"], "Origin": "http://localhost:3000"}
    req = {
        "plan_id": plan,
        "seat_quantity": 1,
        "lines": [
            {"product_id": prod1, "quantity": 1, "line_kind": "ADDON"},
            {"product_id": prod2, "quantity": 1, "line_kind": "ADDON"},
        ],
        "discount_id": disc,
    }
    resp = client.post("/api/v1/pricing/preview", json=req, headers=staff_headers)
    assert resp.status_code == 200
    res = resp.json()
    assert res["subtotal"] == "100.00"
    assert res["total_discount"] == "10.00"
    assert res["taxable_amount"] == "90.00"

    # Line discounts sum to exactly 10.00
    disc_sum = sum(Decimal(l["discount_amount"]) for l in res["lines"])
    assert disc_sum == Decimal("10.00")


def test_pricing_rejects_fabricated_entitlements(client: TestClient, admin_auth, staff_auth):
    """Client cannot fabricate included entitlements for products not bundled in the plan."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    prod = client.post(
        "/api/v1/products",
        json={"name": "Unbundled Addon", "type": "EXTRA", "sales_price": "100.00", "cost_price": "20.00"},
        headers=admin_headers,
    ).json()["id"]

    plan = client.post(
        "/api/v1/plans",
        json={"name": "Strict Plan", "base_fee": "500.00", "minimum_seats": 1, "extra_seat_unit_price": "0.00", "interval": "MONTHLY"},
        headers=admin_headers,
    ).json()["id"]

    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}", "X-CSRF-Token": staff_auth["csrf_token"], "Origin": "http://localhost:3000"}
    req = {
        "plan_id": plan,
        "seat_quantity": 1,
        "lines": [{"product_id": prod, "quantity": 1, "line_kind": "INCLUDED"}],
    }
    resp = client.post("/api/v1/pricing/preview", json=req, headers=staff_headers)
    assert resp.status_code == 422
    err_msg = resp.json().get("detail") or resp.json().get("error", {}).get("message")
    assert "not an included entitlement" in err_msg or "Fabricated entitlements are rejected" in err_msg


def test_pricing_rejects_excess_included_quantities(client: TestClient, admin_auth, staff_auth):
    """Client cannot claim more included units than the plan bundles."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    prod = client.post(
        "/api/v1/products",
        json={"name": "Limited Bundle Item", "type": "STORAGE", "sales_price": "50.00", "cost_price": "10.00"},
        headers=admin_headers,
    ).json()["id"]

    plan = client.post(
        "/api/v1/plans",
        json={
            "name": "Limited Bundle Plan",
            "base_fee": "400.00",
            "minimum_seats": 1,
            "extra_seat_unit_price": "0.00",
            "interval": "MONTHLY",
            "items": [{"ordinal": 1, "product_id": prod, "variant_id": None, "included_quantity": 2}],
        },
        headers=admin_headers,
    ).json()["id"]

    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}", "X-CSRF-Token": staff_auth["csrf_token"], "Origin": "http://localhost:3000"}
    # Requesting 3 when limit is 2
    req = {
        "plan_id": plan,
        "seat_quantity": 1,
        "lines": [{"product_id": prod, "quantity": 3, "line_kind": "INCLUDED"}],
    }
    resp = client.post("/api/v1/pricing/preview", json=req, headers=staff_headers)
    assert resp.status_code == 422
    err_msg = resp.json().get("detail") or resp.json().get("error", {}).get("message")
    assert "exceeds plan" in err_msg and "limit (2)" in err_msg


def test_pricing_rejects_unavailable_plan_by_date(client: TestClient, admin_auth, staff_auth):
    """Plan availability window is authoritatively enforced against supplied business date."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    today = date.today()
    future_start = today + timedelta(days=30)
    future_end = today + timedelta(days=60)

    plan = client.post(
        "/api/v1/plans",
        json={
            "name": "Future Availability Plan",
            "base_fee": "600.00",
            "minimum_seats": 1,
            "extra_seat_unit_price": "0.00",
            "interval": "MONTHLY",
            "available_from": future_start.isoformat(),
            "available_to": future_end.isoformat(),
        },
        headers=admin_headers,
    ).json()["id"]

    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}", "X-CSRF-Token": staff_auth["csrf_token"], "Origin": "http://localhost:3000"}
    # Attempt pricing as of today (before available_from)
    req = {
        "plan_id": plan,
        "seat_quantity": 1,
        "as_of_date": today.isoformat(),
    }
    resp = client.post("/api/v1/pricing/preview", json=req, headers=staff_headers)
    assert resp.status_code == 422
    err_msg = resp.json().get("detail") or resp.json().get("error", {}).get("message")
    assert "not available until" in err_msg

    # Attempt pricing after available_to
    req["as_of_date"] = (future_end + timedelta(days=1)).isoformat()
    resp2 = client.post("/api/v1/pricing/preview", json=req, headers=staff_headers)
    assert resp2.status_code == 422
    err_msg2 = resp2.json().get("detail") or resp2.json().get("error", {}).get("message")
    assert "no longer available" in err_msg2


def test_pricing_requires_reason_for_negotiated_override(client: TestClient, admin_auth, staff_auth):
    """Negotiated agreed_unit_price differing from catalog price requires a non-empty override_reason."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    prod = client.post(
        "/api/v1/products",
        json={"name": "Catalog Item 250", "type": "SERVICE", "sales_price": "250.00", "cost_price": "50.00"},
        headers=admin_headers,
    ).json()["id"]

    plan = client.post(
        "/api/v1/plans",
        json={"name": "Standard Plan Overrides", "base_fee": "500.00", "minimum_seats": 1, "extra_seat_unit_price": "0.00", "interval": "MONTHLY"},
        headers=admin_headers,
    ).json()["id"]

    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}", "X-CSRF-Token": staff_auth["csrf_token"], "Origin": "http://localhost:3000"}
    # 1. Override without reason -> rejected
    req = {
        "plan_id": plan,
        "seat_quantity": 1,
        "lines": [
            {
                "product_id": prod,
                "quantity": 1,
                "line_kind": "ADDON",
                "agreed_unit_price": "180.00",
                "override_reason": None,
            }
        ],
    }
    resp = client.post("/api/v1/pricing/preview", json=req, headers=staff_headers)
    assert resp.status_code == 422
    err_msg = resp.json().get("detail") or resp.json().get("error", {}).get("message")
    assert "override_reason was provided" in err_msg

    # 2. Override with valid reason -> accepted
    req["lines"][0]["override_reason"] = "Enterprise strategic discount approved by VP Sales"
    resp_ok = client.post("/api/v1/pricing/preview", json=req, headers=staff_headers)
    assert resp_ok.status_code == 200
    assert resp_ok.json()["lines"][1]["unit_price"] == "180.00"


def test_pricing_revision_aware_calculation_pins_terms(client: TestClient, admin_auth, staff_auth):
    """Passing discount_revision_id pins exact historical revision terms and returns discount_revision_id."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    today = date.today()
    next_year = today + timedelta(days=365)

    plan = client.post(
        "/api/v1/plans",
        json={"name": "Revision Plan", "base_fee": "1000.00", "minimum_seats": 1, "extra_seat_unit_price": "0.00", "interval": "MONTHLY"},
        headers=admin_headers,
    ).json()["id"]

    # Create discount with Revision 1 (10%)
    disc_res = client.post(
        "/api/v1/discounts",
        json={
            "name": "Versioned Discount Promo",
            "initial_revision": {
                "type": "PERCENT",
                "rate": "10.0000",
                "scope": "SUBSCRIPTION",
                "valid_from": today.isoformat(),
                "valid_to": next_year.isoformat(),
            },
        },
        headers=admin_headers,
    ).json()
    rule_id = disc_res["id"]
    rev1_id = disc_res["current_revision"]["id"]

    # Publish Revision 2 (20%)
    rev2_res = client.post(
        f"/api/v1/discounts/{rule_id}/revisions",
        json={
            "type": "PERCENT",
            "rate": "20.0000",
            "scope": "SUBSCRIPTION",
            "valid_from": today.isoformat(),
            "valid_to": next_year.isoformat(),
        },
        headers=admin_headers,
    ).json()
    rev2_id = rev2_res["current_revision"]["id"]

    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}", "X-CSRF-Token": staff_auth["csrf_token"], "Origin": "http://localhost:3000"}

    # Query using pinned revision 1 ID
    req1 = {
        "plan_id": plan,
        "seat_quantity": 1,
        "discount_revision_id": rev1_id,
    }
    resp1 = client.post("/api/v1/pricing/preview", json=req1, headers=staff_headers)
    assert resp1.status_code == 200
    res1 = resp1.json()
    assert res1["discount_revision_id"] == rev1_id
    assert res1["total_discount"] == "100.00"  # 10% of 1000

    # Query using pinned revision 2 ID
    req2 = {
        "plan_id": plan,
        "seat_quantity": 1,
        "discount_revision_id": rev2_id,
    }
    resp2 = client.post("/api/v1/pricing/preview", json=req2, headers=staff_headers)
    assert resp2.status_code == 200
    res2 = resp2.json()
    assert res2["discount_revision_id"] == rev2_id
    assert res2["total_discount"] == "200.00"  # 20% of 1000
