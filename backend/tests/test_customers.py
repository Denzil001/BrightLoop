import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.security import hash_password, hash_token
from app.models.customers import Customer
from app.models.users import Session as UserSession, User


def _create_auth_client(client: TestClient, db, role: str, email: str, customer_id=None) -> str:
    user = User(
        email_normalized=email,
        name=f"Tester {role}",
        password_hash=hash_password("Valid@Pass123"),
        role=role,
        active=True,
    )
    db.add(user)
    db.flush()

    if role == "CUSTOMER":
        cust = Customer(
            id=customer_id or uuid.uuid4(),
            name="Customer " + email,
            email_normalized=email,
            user_id=user.id,
        )
        db.add(cust)
        db.flush()

    db.commit()

    raw_token = f"tok_{email}"
    raw_csrf = f"csrf_{email}"
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        csrf_hash=hash_token(raw_csrf),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db.add(session)
    db.commit()

    client.cookies.set("brightloop_session", raw_token)
    return raw_csrf


def test_staff_customer_crud_and_search(client: TestClient, db):
    staff_csrf = _create_auth_client(client, db, "STAFF", "ops_staff@brightloop.test")

    # 1. Create operational customer without portal login
    cust_payload = {
        "name": "Acme Global",
        "email": "contact@acmeglobal.test",
        "company": "Acme Global Ltd",
        "phone": "+91 9876543210",
        "billing_address_line1": "123 Market St",
        "billing_city": "Mumbai",
        "billing_state": "Maharashtra",
        "billing_postal_code": "400001",
        "billing_country": "India",
    }
    create_res = client.post(
        "/api/v1/customers",
        headers={"X-CSRF-Token": staff_csrf},
        json=cust_payload,
    )
    assert create_res.status_code == 201
    cust_data = create_res.json()
    assert cust_data["name"] == "Acme Global"
    assert cust_data["has_portal_login"] is False
    customer_id = cust_data["id"]

    # 2. List and search customers
    list_res = client.get("/api/v1/customers?search=Acme&portal_status=unlinked")
    assert list_res.status_code == 200
    list_json = list_res.json()
    assert list_json["total"] >= 1
    assert any(c["id"] == customer_id for c in list_json["items"])

    # 3. Get customer detail
    detail_res = client.get(f"/api/v1/customers/{customer_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["billing_city"] == "Mumbai"

    # 4. Patch customer details
    patch_payload = {
        "company": "Acme Global International Ltd",
        "billing_city": "Navi Mumbai",
        "expected_version": cust_data["version"],
    }
    patch_res = client.patch(
        f"/api/v1/customers/{customer_id}",
        headers={"X-CSRF-Token": staff_csrf},
        json=patch_payload,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["company"] == "Acme Global International Ltd"
    assert patch_res.json()["version"] == cust_data["version"] + 1


def test_customer_isolation_and_own_profile(client: TestClient, db):
    # Customer A
    csrf_a = _create_auth_client(client, db, "CUSTOMER", "customer_a@brightloop.test")

    # Customer A cannot access operational customer list
    res_list = client.get("/api/v1/customers")
    assert res_list.status_code == 403

    # Customer A can access their own profile
    res_profile = client.get("/api/v1/profile")
    assert res_profile.status_code == 200
    profile_data = res_profile.json()
    assert profile_data["email"] == "customer_a@brightloop.test"

    # Customer A updates own profile
    res_patch = client.patch(
        "/api/v1/profile",
        headers={"X-CSRF-Token": csrf_a},
        json={"company": "Customer A Inc", "phone": "+91 9999988888"},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["company"] == "Customer A Inc"
