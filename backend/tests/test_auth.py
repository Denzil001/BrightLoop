from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.security import hash_password, hash_token
from app.models.customers import Customer
from app.models.users import AuthChallenge, Session as UserSession, User


def get_csrf_context(client: TestClient) -> dict:
    """Fetch pre-auth CSRF token and return headers with X-CSRF-Token."""
    res = client.get("/api/v1/auth/csrf")
    assert res.status_code == 200
    token = res.json()["csrf_token"]
    return {"X-CSRF-Token": token}


def test_csrf_endpoint_fresh_browser(client: TestClient, db):
    """
    Regression test: calling GET /api/v1/auth/csrf with empty cookies must generate
    a secure token, bind a PREAUTH_CSRF challenge in PostgreSQL, and set the brightloop_csrf cookie.
    """
    # Ensure no cookies
    client.cookies.clear()

    res = client.get("/api/v1/auth/csrf")
    assert res.status_code == 200
    data = res.json()
    assert "csrf_token" in data
    token = data["csrf_token"]
    assert len(token) > 20
    assert "brightloop_csrf" in res.cookies

    # Verify PostgreSQL binding
    token_h = hash_token(token)
    challenge = db.scalar(
        select(AuthChallenge).where(
            AuthChallenge.token_hash == token_h,
            AuthChallenge.purpose == "PREAUTH_CSRF",
            AuthChallenge.consumed_at.is_(None),
        )
    )
    assert challenge is not None
    assert challenge.delivery_status == "PENDING"


def test_customer_registration_atomic_success(client: TestClient, db):
    headers = get_csrf_context(client)
    email = "reg_test_new@brightloop.test"
    payload = {
        "name": "Alice Customer",
        "email": email,
        "password": "Valid@Password123",
        "company": "Alice Enterprises",
    }
    response = client.post("/api/v1/auth/register", json=payload, headers=headers)
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
    headers = get_csrf_context(client)
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
        res = client.post("/api/v1/auth/register", json=payload, headers=headers)
        assert res.status_code == 422


def test_customer_registration_duplicate_email_conflict(client: TestClient, db):
    headers = get_csrf_context(client)
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
    res = client.post("/api/v1/auth/register", json=payload, headers=headers)
    assert res.status_code == 409
    assert "already exists" in res.json()["error"]["message"]


def test_unlinked_customer_registration_requires_verification(client: TestClient, db):
    headers = get_csrf_context(client)
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
    with patch("app.services.auth.send_customer_verification_email", return_value=True):
        res = client.post("/api/v1/auth/register", json=payload, headers=headers)
    assert res.status_code == 202
    data = res.json()
    assert data["requires_verification"] is True

    # User should NOT be created yet
    assert db.scalar(select(User).where(User.email_normalized == email)) is None

    # Challenge must exist in database with SENT delivery_status
    challenge = db.scalar(
        select(AuthChallenge).where(
            AuthChallenge.email_normalized == email,
            AuthChallenge.purpose == "LINK_SIGNUP",
            AuthChallenge.consumed_at.is_(None),
        )
    )
    assert challenge is not None
    assert challenge.customer_id == op_customer.id
    assert challenge.delivery_status == "SENT"
    assert challenge.delivery_attempts == 1


def test_verify_signup_challenge_consumption(client: TestClient, db):
    headers = get_csrf_context(client)
    email = "verify_link_target@brightloop.test"
    op_customer = Customer(
        name="Target Corp",
        email_normalized=email,
        company="Target Inc",
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
    res = client.post("/api/v1/auth/verify-signup", json={"token": raw_token}, headers=headers)
    assert res.status_code == 200

    # User must now exist and be linked
    user = db.scalar(select(User).where(User.email_normalized == email))
    assert user is not None
    assert user.role == "CUSTOMER"

    db.refresh(op_customer)
    assert op_customer.user_id == user.id

    # Re-using the token must fail
    res_reuse = client.post("/api/v1/auth/verify-signup", json={"token": raw_token}, headers=headers)
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

    csrf_headers = get_csrf_context(client)
    preauth_token = csrf_headers["X-CSRF-Token"]

    # 1. Invalid login
    res_bad = client.post("/api/v1/auth/login", json={"email": email, "password": "Wrong@Password1"}, headers=csrf_headers)
    assert res_bad.status_code == 401

    # 2. Valid login
    res = client.post("/api/v1/auth/login", json={"email": email, "password": password}, headers=csrf_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == email
    session_csrf_token = data["csrf_token"]
    assert session_csrf_token is not None
    # Verify CSRF rotation on login
    assert session_csrf_token != preauth_token
    assert "brightloop_session" in res.cookies

    # Pre-auth challenge must now be consumed
    preauth_challenge = db.scalar(
        select(AuthChallenge).where(
            AuthChallenge.token_hash == hash_token(preauth_token),
            AuthChallenge.purpose == "PREAUTH_CSRF",
        )
    )
    assert preauth_challenge is not None
    assert preauth_challenge.consumed_at is not None

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
        headers={"X-CSRF-Token": session_csrf_token},
        json={"current_password": password, "new_password": "New@Password123"},
    )
    assert pwd_res_ok.status_code == 200

    # 6. Logout without CSRF header should fail 403
    logout_fail = client.post("/api/v1/auth/logout")
    assert logout_fail.status_code == 403

    # 7. Logout with disallowed origin should fail 403
    logout_origin_fail = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": session_csrf_token, "Origin": "http://evil.com"},
    )
    assert logout_origin_fail.status_code == 403

    # 8. Logout with valid CSRF header and allowed origin succeeds
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": session_csrf_token, "Origin": "http://localhost:3000"},
    )
    assert logout_res.status_code == 204

    # 9. Access after logout fails
    me_after = client.get("/api/v1/auth/me")
    assert me_after.status_code == 401


def test_public_auth_mutations_csrf_and_origin_enforcement(client: TestClient):
    """
    Verifies that public authentication mutations enforce:
    - Missing CSRF token -> 403 Forbidden
    - Invalid CSRF token -> 403 Forbidden
    - Disallowed Origin -> 403 Forbidden
    """
    client.cookies.clear()

    # 1. Login without CSRF
    res = client.post("/api/v1/auth/login", json={"email": "nobody@test.com", "password": "Pass@word1"})
    assert res.status_code == 403

    # 2. Login with invalid CSRF
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "Pass@word1"},
        headers={"X-CSRF-Token": "invalid_token_999"},
    )
    assert res.status_code == 403

    # 3. Login with disallowed origin
    valid_headers = get_csrf_context(client)
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "Pass@word1"},
        headers={**valid_headers, "Origin": "http://evil.com"},
    )
    assert res.status_code == 403

    # 4. Register without CSRF
    res = client.post("/api/v1/auth/register", json={"name": "Test", "email": "test@test.com", "password": "Pass@word1"})
    assert res.status_code == 403

    # 5. Register with disallowed Origin
    valid_headers = get_csrf_context(client)
    res = client.post(
        "/api/v1/auth/register",
        json={"name": "Test", "email": "test@test.com", "password": "Pass@word1"},
        headers={**valid_headers, "Origin": "http://evil.com"},
    )
    assert res.status_code == 403


def test_rate_limit_retry_after_header_preservation(client: TestClient):
    """
    Assert that hitting the rate limit produces a 429 response that preserves
    the Retry-After header with a positive integer value and the RATE_LIMITED error code.
    """
    headers = get_csrf_context(client)
    unique_email = f"rate_limit_probe_{int(datetime.now().timestamp())}@brightloop.test"

    # forgot_pwd is rate limited to 5 attempts per window
    hit_429 = False
    for i in range(7):
        res = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": unique_email},
            headers=headers,
        )
        if res.status_code == 429:
            hit_429 = True
            # Verify Retry-After header is preserved
            retry_after = res.headers.get("Retry-After")
            assert retry_after is not None, "Retry-After header missing from 429 response"
            assert int(retry_after) > 0, f"Retry-After must be positive integer, got {retry_after}"

            # Verify structured error code
            data = res.json()
            assert data["error"]["code"] == "RATE_LIMITED"
            assert "Too many attempts" in data["error"]["message"]
            break

    assert hit_429, "Expected 429 Too Many Requests was not triggered"


def test_password_eight_nine_boundary_without_invented_digit_requirement(client, db):
    headers = get_csrf_context(client)
    body = {"name": "Boundary customer", "email": "password_boundary@brightloop.test", "password": "Abcdefg!"}
    assert len(body["password"]) == 8
    assert client.post("/api/v1/auth/register", json=body, headers=headers).status_code == 422
    assert db.scalar(select(User).where(User.email_normalized == body["email"])) is None
    body["password"] = "Abcdefgh!"
    assert len(body["password"]) == 9 and not any(character.isdigit() for character in body["password"])
    response = client.post("/api/v1/auth/register", json=body, headers=headers)
    assert response.status_code == 201, response.text
