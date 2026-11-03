"""Query validation, stable SQL ordering and navigable creation locations."""
from contextlib import nullcontext
from datetime import timedelta
import uuid

import pytest
from sqlalchemy import select

from app.api.v1.endpoints.billing_runs import get_billing_session_factory
from app.core.datetime_utils import get_business_today
from app.main import app
from app.models.customers import Customer
from app.models.invoices import Invoice
from app.services.calendar import boundary
from test_subscriptions import headers
from test_subscriptions import draft_data


@pytest.mark.parametrize("path,valid_sort", [("customers", "name"), ("staff", "email"),
    ("products", "sales_price"), ("plans", "base_fee"), ("taxes", "rate"), ("discounts", "name"),
    ("quotation-templates", "validity_days"), ("subscriptions", "expiry_date"), ("invoices", "total"),
    ("payments", "amount"), ("billing-runs", "as_of_date"), ("reports/details", "date")])
def test_collections_reject_unknown_ambiguous_and_invalid_sort_filters(client, admin_auth, path, valid_sort):
    auth = headers(admin_auth)
    assert client.get(f"/api/v1/{path}?sort={valid_sort}&descending=false", headers=auth).status_code == 200
    for query in ("page_sze=20", "page=1&page=2", "sort=not_a_field", "descending=maybe", "page=0"):
        response = client.get(f"/api/v1/{path}?{query}", headers=auth)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
        assert response.json()["error"]["fields"]


def test_enum_filters_and_view_specific_ordering_are_validated(client, admin_auth):
    auth = headers(admin_auth)
    for path in ("subscriptions?state=NOT_A_STATE", "plans?interval=FORTNIGHTLY", "reports/details?view=active&sort=amount"):
        assert client.get(f"/api/v1/{path}", headers=auth).status_code == 422
    assert client.get("/api/v1/plans?interval=monthly", headers=auth).status_code == 200


def test_customer_sort_has_stable_tie_break_and_page_boundaries(db, client, admin_auth):
    customers = [Customer(name=name, email_normalized=f"sort_{index}@brightloop.test")
        for index, name in enumerate(("Zulu", "Same", "Alpha", "Same"))]
    db.add_all(customers)
    db.commit()
    expected = sorted(customers, key=lambda customer: (customer.name, customer.id))
    observed = []
    for page in range(1, 5):
        response = client.get(f"/api/v1/customers?sort=name&descending=false&page_size=1&page={page}", headers=headers(admin_auth))
        observed.append(response.json()["items"][0]["id"])
    assert observed == [str(customer.id) for customer in expected]
    reverse = client.get("/api/v1/customers?sort=name&descending=true", headers=headers(admin_auth)).json()["items"]
    assert reverse[0]["name"] == "Zulu" and reverse[-1]["name"] == "Alpha"


def test_plan_availability_is_inclusive_and_separate_from_archival(db, client, admin_auth):
    from app.models.catalog import Plan
    today = get_business_today()
    for name, first, last in (("Current", today, today), ("Future", today + timedelta(days=1), None),
                              ("Expired", None, today - timedelta(days=1))):
        db.add(Plan(name=f"Availability {name}", base_fee=100, minimum_seats=1,
            extra_seat_unit_price=0, interval="MONTHLY", available_from=first, available_to=last))
    db.add(Plan(name="Availability Archived", base_fee=100, minimum_seats=1, extra_seat_unit_price=0,
        interval="MONTHLY", available_from=today, available_to=today, active=False))
    db.commit()
    for status, name in (("available", "Current"), ("future", "Future"), ("expired", "Expired")):
        response = client.get(f"/api/v1/plans?availability={status}", headers=headers(admin_auth))
        assert response.status_code == 200, response.text
        expected = ["Availability Archived", "Availability Current"] if status == "available" else [f"Availability {name}"]
        assert [item["name"] for item in response.json()["items"]] == expected
    active = client.get("/api/v1/plans?availability=available&active=true", headers=headers(admin_auth)).json()
    assert [item["name"] for item in active["items"]] == ["Availability Current"]
    assert client.get("/api/v1/plans?availability=unknown", headers=headers(admin_auth)).status_code == 422


def test_discount_management_filters_use_current_revision_dates_and_real_redemptions(db, client, admin_auth, draft_data):
    from app.models.discounts import DiscountRule
    from test_billing import contract
    from app.services.billing import process_next_period
    auth, today = headers(admin_auth), get_business_today()
    product = client.post("/api/v1/products", headers=auth, json={"name": "Eligibility product", "type": "ADDON",
        "sales_price": "100.00", "cost_price": "20.00"}).json()
    rules = {}
    for name in ("eligible", "not_yet_valid", "expired", "exhausted", "disabled"):
        first = today + timedelta(days=1) if name == "not_yet_valid" else today - timedelta(days=30)
        last = today - timedelta(days=1) if name == "expired" else today + timedelta(days=30)
        revision = {"type": "FIXED" if name == "eligible" else "PERCENT", "scope": "PRODUCT" if name == "eligible" else "SUBSCRIPTION",
            "valid_from": first.isoformat(), "valid_to": last.isoformat(),
            **({"amount": "10.00", "product_ids": [product["id"]]} if name == "eligible" else {"rate": "10.00"})}
        response = client.post("/api/v1/discounts", headers=auth, json={"name": f"Eligibility {name}",
            "maximum_uses": 1 if name == "exhausted" else None, "initial_revision": revision})
        assert response.status_code == 201, response.text
        rules[name] = response.json()["id"]
    disabled = db.get(DiscountRule, uuid.UUID(rules["disabled"]))
    disabled.disabled_from = today
    db.commit()
    subscription = contract(db, admin_auth["user"], draft_data, start_date=today,
        expiry_date=today + timedelta(days=90), discount_id=rules["exhausted"])
    process_next_period(db, subscription.id, today)
    db.commit()
    for status, expected_id in rules.items():
        response = client.get(f"/api/v1/discounts?eligibility={status}", headers=auth)
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["items"]] == [expected_id]
    response = client.get("/api/v1/discounts?scope=PRODUCT&discount_type=FIXED", headers=auth)
    assert [item["id"] for item in response.json()["items"]] == [rules["eligible"]]


def test_created_locations_resolve_under_the_same_authorization(db, client, admin_auth, customer_auth):
    auth, today = headers(admin_auth), get_business_today()
    def create(path, body, actor=auth):
        response = client.post(f"/api/v1/{path}", json=body, headers=actor)
        assert response.status_code == 201, response.text
        location = response.headers.get("Location")
        assert location and location.startswith("/api/v1/")
        assert client.get(location, headers=actor).status_code == 200, location
        return response.json()
    customer = create("customers", {"name": "Location customer", "email": customer_auth["user"].email_normalized})
    owned = db.get(Customer, uuid.UUID(customer["id"]))
    owned.user_id = customer_auth["user"].id
    db.commit()
    tax = create("taxes", {"name": "Location GST", "classification": "GST", "rate": "18.00"})
    product = create("products", {"name": "Location product", "type": "SOFTWARE", "sales_price": "100.00", "cost_price": "20.00"})
    variant = create(f"products/{product['id']}/variants", {"name": "Odoo", "price_adjustment": "560.00"})
    assert variant["effective_sales_price"] == "660.00"
    assert client.get(f"/api/v1/products/{uuid.uuid4()}/variants/{variant['id']}", headers=auth).status_code == 404
    plan = create("plans", {"name": "Location plan", "base_fee": "100.00", "minimum_seats": 1,
        "extra_seat_unit_price": "0.00", "interval": "MONTHLY", "tax_rule_ids": [tax["id"]]})
    discount = create("discounts", {"name": "Location discount", "initial_revision": {"type": "PERCENT", "rate": "10.00",
        "scope": "SUBSCRIPTION", "valid_from": today.isoformat(), "valid_to": (today + timedelta(days=365)).isoformat()}})
    create(f"discounts/{discount['id']}/revisions", {"type": "PERCENT", "rate": "15.00", "scope": "SUBSCRIPTION",
        "valid_from": today.isoformat(), "valid_to": (today + timedelta(days=365)).isoformat()})
    create("quotation-templates", {"name": "Location template", "plan_id": plan["id"], "validity_days": 30, "active": False})
    staff = create("staff", {"name": "Location staff", "email": "location_staff@brightloop.test", "initial_password": "Staff@Secure123"})
    assert client.get(f"/api/v1/staff/{staff['id']}", headers=headers(customer_auth)).status_code == 403
    sub = create("subscriptions", {"customer_id": customer["id"], "plan_id": plan["id"], "seat_quantity": 1,
        "start_date": today.isoformat(), "expiry_date": (today + timedelta(days=365)).isoformat()})
    for action in ("ISSUE", "CONFIRM", "ACTIVATE"):
        response = client.post(f"/api/v1/subscriptions/{sub['id']}/commands", headers=auth, json={
            "action": action, "expected_version": sub["version"], "request_key": uuid.uuid4().hex})
        assert response.status_code == 200, response.text
        sub = response.json()
    app.dependency_overrides[get_billing_session_factory] = lambda: lambda: nullcontext(db)
    create("billing-runs", {"as_of_date": today.isoformat(), "subscription_id": sub["id"]})
    invoice = db.scalar(select(Invoice).where(Invoice.subscription_id == uuid.UUID(sub["id"])))
    confirmed = client.post(f"/api/v1/invoices/{invoice.id}/commands", headers=auth, json={"action": "CONFIRM",
        "expected_version": invoice.version, "request_key": uuid.uuid4().hex})
    assert confirmed.status_code == 200, confirmed.text
    create(f"invoices/{invoice.id}/payments", {"amount": "10.00", "method": "CASH", "payment_date": today.isoformat(),
        "note": "Location payment", "request_key": uuid.uuid4().hex})
    sub = client.get(f"/api/v1/subscriptions/{sub['id']}", headers=auth).json()
    create(f"subscriptions/{sub['id']}/requests", {"action": "PAUSE", "effective_date": boundary(today, "MONTHLY", 1).isoformat(),
        "reason": "Location request", "expected_version": sub["version"]}, headers(customer_auth))


def test_registration_location_is_readable_after_signing_in(client):
    csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
    auth = {"X-CSRF-Token": csrf, "Origin": "http://localhost:3000"}
    body = {"name": "Registration location", "email": "registration_location@brightloop.test", "password": "Location@Secure123"}
    created = client.post("/api/v1/auth/register", json=body, headers=auth)
    assert created.status_code == 201
    assert created.headers["Location"] == "/api/v1/auth/me"
    signed_in = client.post("/api/v1/auth/login", json={"email": body["email"], "password": body["password"]}, headers=auth)
    assert signed_in.status_code == 200, signed_in.text
    read = client.get(created.headers["Location"])
    assert read.status_code == 200 and read.json()["id"] == created.json()["user"]["id"]
