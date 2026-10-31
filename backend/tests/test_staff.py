from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.security import hash_password, hash_token
from app.models.users import Session as UserSession, User


def _create_authenticated_client(client: TestClient, db, role: str, email: str) -> str:
    user = User(
        email_normalized=email,
        name=f"Test {role}",
        password_hash=hash_password("Valid@Pass123"),
        role=role,
        active=True,
    )
    db.add(user)
    db.commit()

    raw_token = f"session_token_{email}"
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


def test_admin_can_create_and_list_staff(client: TestClient, db):
    admin_csrf = _create_authenticated_client(client, db, "ADMIN", "admin_staff_tester@brightloop.test")

    # 1. Admin creates staff
    staff_payload = {
        "name": "Bob Staff",
        "email": "bob_staff@brightloop.test",
        "initial_password": "Staff@Password123",
    }
    create_res = client.post(
        "/api/v1/staff",
        headers={"X-CSRF-Token": admin_csrf},
        json=staff_payload,
    )
    assert create_res.status_code == 201
    staff_data = create_res.json()
    assert staff_data["role"] == "STAFF"
    assert staff_data["active"] is True

    # 2. Admin lists staff
    list_res = client.get("/api/v1/staff?search=bob")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 1
    assert any(s["email"] == "bob_staff@brightloop.test" for s in list_data["items"])


def test_staff_and_customer_forbidden_from_staff_endpoints(client: TestClient, db):
    # Staff role attempting to access staff management
    staff_csrf = _create_authenticated_client(client, db, "STAFF", "non_admin_staff@brightloop.test")
    res_list = client.get("/api/v1/staff")
    assert res_list.status_code == 403

    res_create = client.post(
        "/api/v1/staff",
        headers={"X-CSRF-Token": staff_csrf},
        json={"name": "Forbidden", "email": "forbidden@brightloop.test", "initial_password": "Valid@Pass123"},
    )
    assert res_create.status_code == 403


def test_admin_deactivate_staff_revokes_sessions(client: TestClient, db):
    admin_csrf = _create_authenticated_client(client, db, "ADMIN", "super_admin@brightloop.test")

    # Create target staff user
    staff_email = "target_staff_deact@brightloop.test"
    staff_user = User(
        email_normalized=staff_email,
        name="Target Staff",
        password_hash=hash_password("Pass@12345"),
        role="STAFF",
        active=True,
    )
    db.add(staff_user)
    db.commit()

    # Create active session for target staff
    staff_session_token = "staff_live_session_123"
    staff_session = UserSession(
        user_id=staff_user.id,
        token_hash=hash_token(staff_session_token),
        csrf_hash=hash_token("csrf"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    db.add(staff_session)
    db.commit()

    # Deactivate staff
    deact_res = client.post(
        f"/api/v1/staff/{staff_user.id}/deactivate",
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert deact_res.status_code == 200

    # Verify database state
    db.refresh(staff_user)
    assert staff_user.active is False
    db.refresh(staff_session)
    assert staff_session.revoked_at is not None

    # Now verify that a request using staff_session_token is rejected
    test_client_staff = TestClient(client.app)
    test_client_staff.cookies.set("brightloop_session", staff_session_token)
    res_me = test_client_staff.get("/api/v1/auth/me")
    assert res_me.status_code == 401
