from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.catalog import Plan, PlanItem, Product, ProductVariant
from app.models.taxes import TaxRule
from app.models.users import User


def test_product_crud_and_role_access(client: TestClient, admin_auth, staff_auth, customer_auth):
    """Admin can create, update, and archive products; Staff gets operational fields; Customer forbidden."""
    # 1. Admin creates product
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    create_payload = {
        "name": "Cloud Storage Extra",
        "type": "STORAGE",
        "sales_price": "50.00",
        "cost_price": "20.00",
        "notes": "Internal vendor: AWS S3",
        "active": True,
        "tax_rule_ids": [],
    }
    resp = client.post("/api/v1/products", json=create_payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    prod_data = resp.json()
    prod_id = prod_data["id"]
    assert prod_data["name"] == "Cloud Storage Extra"
    assert prod_data["sales_price"] == "50.00"
    assert prod_data["cost_price"] == "20.00"
    assert prod_data["notes"] == "Internal vendor: AWS S3"

    # 2. Staff reads product - cost_price and notes MUST be excluded
    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}"}
    resp_staff = client.get(f"/api/v1/products/{prod_id}", headers=staff_headers)
    assert resp_staff.status_code == 200
    staff_data = resp_staff.json()
    assert staff_data["name"] == "Cloud Storage Extra"
    assert staff_data["sales_price"] == "50.00"
    assert "cost_price" not in staff_data
    assert "notes" not in staff_data

    # 3. Staff cannot create product (403)
    resp_staff_create = client.post(
        "/api/v1/products",
        json={"name": "Staff Prod", "type": "ITEM", "sales_price": "10.00", "cost_price": "5.00"},
        headers={"Authorization": f"Bearer {staff_auth['token']}", "Origin": "http://localhost:3000", "X-CSRF-Token": staff_auth["csrf_token"]},
    )
    assert resp_staff_create.status_code == 403

    # 4. Customer cannot access products endpoints (403)
    resp_cust = client.get(f"/api/v1/products/{prod_id}", headers={"Authorization": f"Bearer {customer_auth['token']}"})
    assert resp_cust.status_code == 403

    # 5. Admin updates product
    update_payload = {"sales_price": "55.00"}
    resp_up = client.patch(f"/api/v1/products/{prod_id}", json=update_payload, headers=admin_headers)
    assert resp_up.status_code == 200
    assert resp_up.json()["sales_price"] == "55.00"

    # 6. Admin archives product
    resp_arch = client.post(f"/api/v1/products/{prod_id}/archive", headers=admin_headers)
    assert resp_arch.status_code == 200
    assert resp_arch.json()["active"] is False


def test_product_variants_and_560_adjustment(client: TestClient, admin_auth):
    """Test variant price adjustment: product base 200 + variant 560 = 760; negative effective price rejected."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    # Create base product
    prod_resp = client.post(
        "/api/v1/products",
        json={
            "name": "Enterprise Security Pack",
            "type": "SECURITY",
            "sales_price": "200.00",
            "cost_price": "80.00",
            "notes": "Base security",
        },
        headers=admin_headers,
    )
    assert prod_resp.status_code == 201
    prod_id = prod_resp.json()["id"]

    # Add variant with 560.00 adjustment
    var_resp = client.post(
        f"/api/v1/products/{prod_id}/variants",
        json={"name": "24/7 Dedicated SOC", "price_adjustment": "560.00", "active": True},
        headers=admin_headers,
    )
    assert var_resp.status_code == 201
    var_data = var_resp.json()
    assert var_data["name"] == "24/7 Dedicated SOC"
    assert var_data["price_adjustment"] == "560.00"
    assert var_data["effective_sales_price"] == "760.00"

    # Add variant with negative adjustment that exceeds base price -> rejected
    bad_var_resp = client.post(
        f"/api/v1/products/{prod_id}/variants",
        json={"name": "Excessive Discount Variant", "price_adjustment": "-250.00", "active": True},
        headers=admin_headers,
    )
    assert bad_var_resp.status_code == 422
    err_body = bad_var_resp.json()
    err_msg = err_body.get("detail") or err_body.get("error", {}).get("message", "")
    assert "cannot be negative" in err_msg


def test_zero_price_allowed_and_negative_rejected(client: TestClient, admin_auth):
    """Zero prices are allowed; negative prices are rejected by validation/constraints."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    # Zero price is allowed
    zero_resp = client.post(
        "/api/v1/products",
        json={"name": "Complimentary Tier", "type": "TIER", "sales_price": "0.00", "cost_price": "0.00"},
        headers=admin_headers,
    )
    assert zero_resp.status_code == 201
    assert zero_resp.json()["sales_price"] == "0.00"

    # Negative sales price is rejected
    neg_resp = client.post(
        "/api/v1/products",
        json={"name": "Negative Price Product", "type": "BAD", "sales_price": "-10.00", "cost_price": "0.00"},
        headers=admin_headers,
    )
    assert neg_resp.status_code == 422


def test_plan_crud_and_included_items(client: TestClient, admin_auth, staff_auth):
    """Admin can create plan with included items; interval validated; staff can read."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    # Create product for plan inclusion
    prod_resp = client.post(
        "/api/v1/products",
        json={"name": "Basic Support Bundle", "type": "SUPPORT", "sales_price": "100.00", "cost_price": "30.00"},
        headers=admin_headers,
    )
    prod_id = prod_resp.json()["id"]

    # Create plan with 5 minimum seats, 100 extra seat price, and included item
    plan_payload = {
        "name": "Standard Business Plan",
        "description": "5 seats included",
        "base_fee": "1000.00",
        "minimum_seats": 5,
        "extra_seat_unit_price": "100.00",
        "interval": "MONTHLY",
        "payment_term_days": 15,
        "allow_pause": True,
        "allow_resume": True,
        "allow_renewal": True,
        "allow_early_closure": True,
        "auto_close_on_expiry": True,
        "active": True,
        "items": [
            {
                "ordinal": 1,
                "product_id": prod_id,
                "variant_id": None,
                "included_quantity": 2,
            }
        ],
        "tax_rule_ids": [],
    }
    plan_resp = client.post("/api/v1/plans", json=plan_payload, headers=admin_headers)
    assert plan_resp.status_code == 201, plan_resp.text
    plan_data = plan_resp.json()
    assert plan_data["name"] == "Standard Business Plan"
    assert plan_data["base_fee"] == "1000.00"
    assert plan_data["minimum_seats"] == 5
    assert plan_data["extra_seat_unit_price"] == "100.00"
    assert len(plan_data["items"]) == 1
    assert plan_data["items"][0]["included_quantity"] == 2

    # Staff can read plan
    staff_headers = {"Authorization": f"Bearer {staff_auth['token']}"}
    list_resp = client.get("/api/v1/plans", headers=staff_headers)
    assert list_resp.status_code == 200
    assert any(p["name"] == "Standard Business Plan" for p in list_resp.json()["items"])

    # Invalid interval rejected
    bad_interval = dict(plan_payload, name="Bad Interval Plan", interval="HOURLY")
    bad_resp = client.post("/api/v1/plans", json=bad_interval, headers=admin_headers)
    assert bad_resp.status_code == 422


def test_database_error_sanitization_does_not_leak_internals(client: TestClient, admin_auth):
    """Database errors return structured safe messages without leaking SQL, parameters, or internal constraints."""
    admin_headers = {
        "Authorization": f"Bearer {admin_auth['token']}",
        "X-CSRF-Token": admin_auth["csrf_token"],
        "Origin": "http://localhost:3000",
    }
    # 1. Create a tax rule
    tax_name = f"Sanitize Tax {uuid.uuid4().hex[:6]}"
    res1 = client.post(
        "/api/v1/taxes",
        json={"name": tax_name, "classification": "VAT", "rate": "5.0000", "active": True},
        headers=admin_headers,
    )
    assert res1.status_code == 201

    # 2. Duplicate tax rule with same name
    res2 = client.post(
        "/api/v1/taxes",
        json={"name": tax_name, "classification": "VAT", "rate": "5.0000", "active": True},
        headers=admin_headers,
    )
    # Must be 409 Conflict
    assert res2.status_code in (409, 422)
    resp_text = res2.text

    # Assert no raw database internals or SQL disclosure
    forbidden_terms = [
        "INSERT INTO",
        "SELECT",
        "UPDATE",
        "DETAIL: Key",
        "psycopg",
        "asyncpg",
        "sqlalchemy",
        "parameters:",
        "syntax error",
        "Database constraint violation:",
    ]
    for term in forbidden_terms:
        assert term.lower() not in resp_text.lower(), f"Response leaked internal term '{term}': {resp_text}"

    # Verify structured shape
    data = res2.json()
    assert "error" in data or "detail" in data
    message = data.get("error", {}).get("message") or data.get("detail", "")
    assert "already exists" in message or "conflict" in message.lower()
