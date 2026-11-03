"""HTTP validation and PostgreSQL boundary regressions, before writes occur."""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.datetime_utils import get_business_today
from app.core.security import verify_password
from app.models.catalog import Plan, Product
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.users import User
from app.services.financial_calculator import PricingError, round_money


def headers(auth):
    return {"Authorization": f"Bearer {auth['token']}", "X-CSRF-Token": auth["csrf_token"], "Origin": "http://localhost:3000"}


@pytest.fixture
def records(db):
    product = Product(name="Boundary product", type="ADDON", sales_price=10, cost_price=0)
    plan = Plan(name="Boundary plan", base_fee=100, minimum_seats=1, extra_seat_unit_price=0, interval="MONTHLY")
    db.add_all([product, plan])
    db.commit()
    return {"product_id": str(product.id), "plan_id": str(plan.id)}


@pytest.mark.parametrize("endpoint,payload,field", [
    ("/customers", {"name": " \t ", "email": "boundary@brightloop.test"}, "name"),
    ("/staff", {"name": " ", "email": "boundary@brightloop.test", "initial_password": "Staff@Secure123"}, "name"),
    ("/products", {"name": " ", "type": "ADDON", "sales_price": "10", "cost_price": "0"}, "name"),
    ("/products", {"name": "Boundary", "type": " ", "sales_price": "10", "cost_price": "0"}, "type"),
    ("/products/{product_id}/variants", {"name": " ", "price_adjustment": "0"}, "name"),
    ("/plans", {"name": " ", "base_fee": "100", "interval": "MONTHLY"}, "name"),
    ("/taxes", {"name": " ", "classification": "GST", "rate": "18"}, "name"),
    ("/taxes", {"name": "Boundary", "classification": " ", "rate": "18"}, "classification"),
    ("/quotation-templates", {"name": " ", "plan_id": "{plan_id}", "active": False}, "name"),
    ("/products", {"name": "Boundary", "type": "ADDON", "sales_price": "10000000000000000.00", "cost_price": "0"}, "sales_price"),
    ("/products", {"name": "Boundary", "type": "ADDON", "sales_price": "1.001", "cost_price": "0"}, "sales_price"),
    ("/products", {"name": "Boundary", "type": "ADDON", "sales_price": 0.1, "cost_price": "0"}, "sales_price"),
    ("/products", {"name": "Boundary", "type": "ADDON", "sales_price": "1", "cost_price": "NaN"}, "cost_price"),
    ("/products/{product_id}/variants", {"name": "Boundary", "price_adjustment": "Infinity"}, "price_adjustment"),
    ("/plans", {"name": "Boundary", "base_fee": "10000000000000000", "interval": "MONTHLY"}, "base_fee"),
    ("/plans", {"name": "Boundary", "base_fee": "100", "extra_seat_unit_price": "1.001", "interval": "MONTHLY"}, "extra_seat_unit_price"),
    ("/plans", {"name": "Boundary", "base_fee": "100", "minimum_seats": 2147483648, "interval": "MONTHLY"}, "minimum_seats"),
    ("/taxes", {"name": "Boundary", "classification": "GST", "rate": "18.12345"}, "rate"),
    ("/quotation-templates", {"name": "Boundary", "plan_id": "{plan_id}", "validity_days": 366, "active": False}, "validity_days"),
])
def test_invalid_required_and_numeric_inputs_rejected(client, db, admin_auth, records, endpoint, payload, field):
    body = {key: value.format(**records) if isinstance(value, str) else value for key, value in payload.items()}
    before = db.scalar(select(func.count()).select_from(Product))
    response = client.post(f"/api/v1{endpoint.format(**records)}", json=body, headers=headers(admin_auth))
    assert response.status_code == 422, response.text
    assert any(item["path"].split(".")[-1] == field for item in response.json()["error"]["fields"])
    assert db.scalar(select(func.count()).select_from(Product)) == before


def test_whitespace_signup_rejected_and_password_whitespace_preserved(client, db):
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    auth = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
    payload = {"name": " ", "email": "boundary_signup@brightloop.test", "password": "  Good@Pass123  "}
    before = (db.scalar(select(func.count()).select_from(User)), db.scalar(select(func.count()).select_from(Customer)))
    assert client.post("/api/v1/auth/register", json=payload, headers=auth).status_code == 422
    assert before == (db.scalar(select(func.count()).select_from(User)), db.scalar(select(func.count()).select_from(Customer)))
    payload["name"] = "  Boundary customer  "
    response = client.post("/api/v1/auth/register", json=payload, headers=auth)
    assert response.status_code == 201, response.text
    user = db.scalar(select(User).where(User.email_normalized == payload["email"]))
    assert user.name == "Boundary customer"
    assert verify_password(payload["password"], user.password_hash)
    assert not verify_password(payload["password"].strip(), user.password_hash)


def test_money_maximum_round_trip_and_explicit_null_update(client, db, admin_auth, records):
    response = client.post("/api/v1/products", json={"name": "  Exact maximum  ", "type": "  ADDON ",
        "sales_price": "9999999999999999.99", "cost_price": "90071992547409.91"}, headers=headers(admin_auth))
    assert response.status_code == 201, response.text
    product = response.json()
    assert product["name"] == "Exact maximum" and product["type"] == "ADDON"
    assert product["sales_price"] == "9999999999999999.99" and product["cost_price"] == "90071992547409.91"
    for payload in ({"name": " "}, {"name": None}, {"sales_price": None}):
        failed = client.patch(f"/api/v1/products/{product['id']}", json=payload, headers=headers(admin_auth))
        assert failed.status_code == 422, failed.text
    assert client.get(f"/api/v1/products/{product['id']}", headers=headers(admin_auth)).json()["sales_price"] == product["sales_price"]


@pytest.mark.parametrize("kind,value", [("amount", "1.001"), ("minimum_purchase", "10000000000000000"), ("rate", "18.12345")])
def test_discount_precision_rejected(client, admin_auth, kind, value):
    today = get_business_today()
    revision = {"type": "PERCENT" if kind == "rate" else "FIXED", "scope": "SUBSCRIPTION",
                "valid_from": today.isoformat(), "valid_to": (today + timedelta(days=365)).isoformat(),
                "rate" if kind == "rate" else "amount": "10"}
    revision[kind] = value
    response = client.post("/api/v1/discounts", json={"name": "Boundary discount", "initial_revision": revision}, headers=headers(admin_auth))
    assert response.status_code == 422, response.text
    assert any(item["path"].endswith(kind) for item in response.json()["error"]["fields"])


def test_computed_overflow_is_validation_error_not_decimal_or_database_failure(client, db, admin_auth, records):
    maximum = client.patch(f"/api/v1/products/{records['product_id']}", json={"sales_price": "9999999999999999.99"}, headers=headers(admin_auth))
    assert maximum.status_code == 200
    response = client.post("/api/v1/pricing/preview", json={"plan_id": records["plan_id"], "seat_quantity": 1,
        "lines": [{"product_id": records["product_id"], "quantity": 2147483647}]}, headers=headers(admin_auth))
    assert response.status_code == 422, response.text
    assert "monetary range" in response.text
    assert db.scalar(select(func.count()).select_from(Invoice)) == 0
    with pytest.raises(PricingError, match="monetary range"):
        round_money(Decimal("1e1000"))


def test_effective_variant_price_bounds_hold_on_either_edit_path(client, admin_auth):
    auth = headers(admin_auth)
    product = client.post("/api/v1/products", headers=auth, json={"name": "Effective maximum", "type": "ADDON", "sales_price": "0.00", "cost_price": "0.00"}).json()
    url = f"/api/v1/products/{product['id']}"
    variant = client.post(f"{url}/variants", headers=auth, json={"name": "Maximum adjustment", "price_adjustment": "9999999999999999.99"})
    assert variant.status_code == 201, variant.text
    assert client.patch(url, headers=auth, json={"sales_price": "0.01"}).status_code == 422
    assert client.get(url, headers=auth).json()["sales_price"] == "0.00"
    assert client.patch(f"{url}/variants/{variant.json()['id']}", headers=auth, json={"price_adjustment": "-0.01"}).status_code == 422
    client.patch(f"{url}/variants/{variant.json()['id']}", headers=auth, json={"price_adjustment": "0.00"})
    assert client.patch(url, headers=auth, json={"sales_price": "9999999999999999.99"}).status_code == 200
    assert client.post(f"{url}/variants", headers=auth, json={"name": "Overflow", "price_adjustment": "0.01"}).status_code == 422
