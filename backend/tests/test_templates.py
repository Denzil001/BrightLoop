from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient


def test_quotation_template_crud_and_validation(client: TestClient, admin_auth, staff_auth):
    """Admin can create quotation templates with lines; incomplete cannot be active; Staff can read."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    # Create product and plan first
    prod_resp = client.post(
        "/api/v1/products",
        json={"name": "Analytics Pro Module", "type": "MODULE", "sales_price": "150.00", "cost_price": "50.00"},
        headers=admin_headers,
    )
    prod_id = prod_resp.json()["id"]

    plan_resp = client.post(
        "/api/v1/plans",
        json={
            "name": "Template Plan",
            "base_fee": "500.00",
            "minimum_seats": 2,
            "extra_seat_unit_price": "50.00",
            "interval": "MONTHLY",
        },
        headers=admin_headers,
    )
    plan_id = plan_resp.json()["id"]

    # 1. Create template with lines
    template_payload = {
        "name": "Standard Onboarding Template",
        "description": "Standard startup bundle",
        "plan_id": plan_id,
        "validity_days": 45,
        "active": True,
        "lines": [
            {
                "ordinal": 1,
                "product_id": prod_id,
                "variant_id": None,
                "quantity": 1,
                "line_kind": "ADDON",
            }
        ],
    }
    resp = client.post("/api/v1/quotation-templates", json=template_payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    tpl_data = resp.json()
    tpl_id = tpl_data["id"]
    assert tpl_data["name"] == "Standard Onboarding Template"
    assert tpl_data["validity_days"] == 45
    assert len(tpl_data["lines"]) == 1
    assert tpl_data["lines"][0]["line_kind"] == "ADDON"

    # 2. Staff can read templates
    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}"}
    staff_resp = client.get(f"/api/v1/quotation-templates/{tpl_id}", headers=staff_headers)
    assert staff_resp.status_code == 200
    assert staff_resp.json()["name"] == "Standard Onboarding Template"

    # 3. Incomplete template cannot be active on creation
    bad_tpl = {
        "name": "Empty Incomplete Template",
        "plan_id": plan_id,
        "validity_days": 30,
        "active": True,
        "lines": [],
    }
    resp_empty = client.post("/api/v1/quotation-templates", json=bad_tpl, headers=admin_headers)
    assert resp_empty.status_code == 422
    err_msg = resp_empty.json().get("detail") or resp_empty.json().get("error", {}).get("message")
    assert "at least one line" in err_msg


def test_template_patch_clearing_lines_while_omitting_active_is_rejected(client: TestClient, admin_auth):
    """Patching lines to empty while active is True (even when active is omitted in payload) must be rejected."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    prod = client.post(
        "/api/v1/products",
        json={"name": "Module A", "type": "MODULE", "sales_price": "100.00", "cost_price": "20.00"},
        headers=admin_headers,
    ).json()["id"]

    plan = client.post(
        "/api/v1/plans",
        json={"name": "Plan A", "base_fee": "200.00", "minimum_seats": 1, "extra_seat_unit_price": "0.00", "interval": "MONTHLY"},
        headers=admin_headers,
    ).json()["id"]

    # Create active template with 1 line
    tpl = client.post(
        "/api/v1/quotation-templates",
        json={
            "name": "Active Template A",
            "plan_id": plan,
            "validity_days": 30,
            "active": True,
            "lines": [{"ordinal": 1, "product_id": prod, "quantity": 1, "line_kind": "ADDON"}],
        },
        headers=admin_headers,
    ).json()
    tpl_id = tpl["id"]
    assert tpl["active"] is True

    # Attempt to clear lines while omitting 'active' in payload
    patch_resp = client.patch(
        f"/api/v1/quotation-templates/{tpl_id}",
        json={"lines": []},
        headers=admin_headers,
    )
    assert patch_resp.status_code == 422
    err_msg = patch_resp.json().get("detail") or patch_resp.json().get("error", {}).get("message")
    assert "at least one line" in err_msg


def test_template_rejects_inactive_referenced_catalog(client: TestClient, admin_auth):
    """Quotation template cannot reference inactive/archived plans or products."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    prod = client.post(
        "/api/v1/products",
        json={"name": "Archivable Product", "type": "MODULE", "sales_price": "100.00", "cost_price": "20.00"},
        headers=admin_headers,
    ).json()["id"]

    plan = client.post(
        "/api/v1/plans",
        json={"name": "Archivable Plan", "base_fee": "200.00", "minimum_seats": 1, "extra_seat_unit_price": "0.00", "interval": "MONTHLY"},
        headers=admin_headers,
    ).json()["id"]

    # Archive the product
    client.post(f"/api/v1/products/{prod}/archive", headers=admin_headers)

    # Attempt to create template referencing archived product
    resp = client.post(
        "/api/v1/quotation-templates",
        json={
            "name": "Template with Inactive Product",
            "plan_id": plan,
            "validity_days": 30,
            "active": False,
            "lines": [{"ordinal": 1, "product_id": prod, "quantity": 1, "line_kind": "ADDON"}],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422
    err_msg = resp.json().get("detail") or resp.json().get("error", {}).get("message")
    assert "archived/inactive" in err_msg
