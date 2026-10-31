from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.security import hash_password, hash_token
from app.models.customers import Customer
from app.models.users import AuthChallenge, Session as UserSession, User


def test_customer_registration_atomic_success(client: TestClient, db):
    email = "reg_test_new@brightloop.test"
    payload = {
        "name": "Alice Customer",
        "email": email,
        "password": "Valid@Password123",
        "company": "Alice Enterprises",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["requires_verification"] is False
    assert data["user"]["email"] == email
    assert data["user"]["role"] == "CUSTOMER"

    # Verify database persistence
    user = db.scalar(select(User).where(User.email_normalized == email))
    assert user is not None
    assert user.role == "CUSTOMER"
    customer = db.scalar(select(Customer).where(Customer.email_normalized == email))
    assert customer is not None
    assert customer.user_id == user.id
    assert customer.company == "Alice Enterprises"


def test_customer_registration_password_complexity_failure(client: TestClient):
    bad_passwords = [
        "short",  # < 9 chars
        "alllowercase123!",  # no uppercase
        "ALLUPPERCASE123!",  # no lowercase
        "NoSpecialChar123",  # no special char
    ]
    for pwd in bad_passwords:
        payload = {
            "name": "Bad Pwd User",
            "email": f"bad_{abs(hash(pwd))}@brightloop.test",
            "password": pwd,
        }
        res = client.post("/api/v1/auth/register", json=payload)
        assert res.status_code == 422


def test_customer_registration_duplicate_email_conflict(client: TestClient, db):
    email = "duplicate@brightloop.test"
    user = User(
        email_normalized=email,
        name="Existing User",
        password_hash=hash_password("Valid@Pass123"),
        role="CUSTOMER",
        active=True,
    )
    db.add(user)
    db.commit()

    payload = {
        "name": "Impostor",
        "email": email,
        "password": "Another@Password123",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 409
    assert "already exists" in res.json()["error"]["message"]


def test_unlinked_customer_registration_requires_verification(client: TestClient, db):
    email = "unlinked_ops@brightloop.test"
    # Create operational customer without portal login
    op_customer = Customer(
        name="Operational Corp",
        email_normalized=email,
        company="Op Corp Inc",
        user_id=None,
    )
    db.add(op_customer)
    db.commit()

    # User attempts to register with this operational customer email
    payload = {
        "name": "Op Account Holder",
        "email": email,
        "password": "Secure@Linking123",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 202
    data = res.json()
    assert data["requires_verification"] is True

    # User should NOT be created yet
    assert db.scalar(select(User).where(User.email_normalized == email)) is None

    # Challenge must exist in database
    challenge = db.scalar(
        select(AuthChallenge).where(
            AuthChallenge.email_normalized == email,
            AuthChallenge.purpose == "LINK_SIGNUP",
        )
    )
    assert challenge is not None
    assert challenge.customer_id == op_customer.id
    assert challenge.consumed_at is None


def test_verify_signup_challenge_consumption(client: TestClient, db):
    email = "verify_link_target@brightloop.test"
    op_customer = Customer(
        name="Target Corp",
        email_normalized=email,
        user_id=None,
    )
    db.add(op_customer)
    db.commit()

    raw_token = "valid_secure_link_token_1234567890"
    challenge = AuthChallenge(
        purpose="LINK_SIGNUP",
        token_hash=hash_token(raw_token),
        email_normalized=email,
        customer_id=op_customer.id,
        pending_name="Target Owner",
        pending_password_hash=hash_password("Linked@Pass123"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(challenge)
    db.commit()

    # Verify with token
    res = client.post("/api/v1/auth/verify-signup", json={"token": raw_token})
    assert res.status_code == 200

    # User must now exist and be linked
    user = db.scalar(select(User).where(User.email_normalized == email))
    assert user is not None
    assert user.role == "CUSTOMER"

    db.refresh(op_customer)
    assert op_customer.user_id == user.id

    # Re-using the token must fail
    res_reuse = client.post("/api/v1/auth/verify-signup", json={"token": raw_token})
    assert res_reuse.status_code == 400


def test_login_logout_and_session_lifecycle(client: TestClient, db):
    email = "session_user@brightloop.test"
    password = "My@Password123"
    user = User(
        email_normalized=email,
        name="Session Tester",
        password_hash=hash_password(password),
        role="STAFF",
        active=True,
    )
    db.add(user)
    db.commit()

    # 1. Invalid login
    res_bad = client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong@Password1"})
    assert res_bad.status_code == 401

    # 2. Valid login
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == email
    csrf_token = data["csrf_token"]
    assert csrf_token is not None
    assert "brightloop_session" in res.cookies

    # 3. GET /me with session cookie
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["email"] == email

    # 4. State-changing request without CSRF should fail 403
    pwd_res = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": password, "new_password": "New@Password123"},
    )
    assert pwd_res.status_code == 403

    # 5. State-changing request with valid CSRF header succeeds
    pwd_res_ok = client.post(
        "/api/v1/auth/change-password",
        headers={"X-CSRF-Token": csrf_token},
        json={"current_password": password, "new_password": "New@Password123"},
    )
    assert pwd_res_ok.status_code == 200

    # 6. Logout
    logout_res = client.post("/api/v1/auth/logout")
    assert logout_res.status_code == 204

    # 7. Access after logout fails
    me_after = client.get("/api/v1/auth/me")
    assert me_after.status_code == 401
