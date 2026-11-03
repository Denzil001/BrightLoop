"""Authenticated transport policy must cover every declared domain operation."""
import pytest
from sqlalchemy import func, select

from app.core.datetime_utils import get_business_today
from app.models.catalog import Plan
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.models.users import User


def headers(auth, origin="http://localhost:3000"):
    return {"Authorization": f"Bearer {auth['token']}", "X-CSRF-Token": auth["csrf_token"], "Origin": origin}


@pytest.mark.parametrize("path,payload", [
    ("/staff", {"name": "Foreign origin staff", "email": "foreign_staff@brightloop.test", "initial_password": "Staff@Secure123"}),
    ("/customers", {"name": "Foreign origin customer", "email": "foreign_customer@brightloop.test"}),
])
def test_legacy_creates_reject_foreign_origin_even_with_valid_csrf(db, client, admin_auth, path, payload):
    before = [db.scalar(select(func.count()).select_from(model)) for model in (User, Customer)]
    response = client.post(f"/api/v1{path}", json=payload, headers=headers(admin_auth, "https://untrusted.example"))
    assert response.status_code == 403
    assert "cross-origin" in response.json()["error"]["message"].lower()
    assert [db.scalar(select(func.count()).select_from(model)) for model in (User, Customer)] == before


def test_profile_rejects_foreign_origin_without_changing_identity(db, client, customer_auth):
    user = customer_auth["user"]
    customer = Customer(name="Original profile", email_normalized=user.email_normalized, user_id=user.id)
    db.add(customer)
    db.commit()
    response = client.patch("/api/v1/profile", json={"name": "Unexpected replacement"},
                            headers=headers(customer_auth, "https://untrusted.example"))
    assert response.status_code == 403
    db.refresh(customer)
    db.refresh(user)
    assert customer.name == "Original profile" and user.name == "Customer Fixture"


@pytest.mark.parametrize("violation", ["missing_csrf", "foreign_origin"])
def test_preview_transport_guard_and_side_effect_free_success(db, client, admin_auth, violation):
    plan = Plan(name="Transport preview", base_fee=100, minimum_seats=1, extra_seat_unit_price=0, interval="MONTHLY")
    db.add(plan)
    db.commit()
    payload = {"plan_id": str(plan.id), "seat_quantity": 1, "as_of_date": get_business_today().isoformat(), "lines": []}
    supplied = headers(admin_auth)
    if violation == "missing_csrf":
        supplied.pop("X-CSRF-Token")
    else:
        supplied["Origin"] = "https://untrusted.example"
    before = db.scalar(select(func.count()).select_from(Invoice))
    assert client.post("/api/v1/pricing/preview", json=payload, headers=supplied).status_code == 403
    valid = client.post("/api/v1/pricing/preview", json=payload, headers=headers(admin_auth))
    assert valid.status_code == 200 and valid.json()["total"] == "100.00"
    assert db.scalar(select(func.count()).select_from(Invoice)) == before


def test_all_domain_route_guards_are_declared():
    from scripts.audit_route_security import audit_routes
    result = audit_routes()
    assert result["protected_domain_routes_checked"] >= 50
    assert result["mutation_routes_checked"] >= 20
    assert result["issues"] == []
