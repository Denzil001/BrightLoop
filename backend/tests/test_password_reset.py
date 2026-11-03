from datetime import datetime, timezone, timedelta
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.security import hash_password, hash_token, verify_password
from app.models.customers import Customer
from app.models.users import AuthChallenge, Session as UserSession, User


def get_csrf_context(client: TestClient) -> dict:
    """Fetch pre-auth CSRF token and return headers with X-CSRF-Token."""
    res = client.get("/api/v1/auth/csrf")
    assert res.status_code == 200
    token = res.json()["csrf_token"]
    return {"X-CSRF-Token": token}


def test_forgot_password_generic_acceptance(client: TestClient):
    headers = get_csrf_context(client)
    # Tests that /forgot-password always returns 202 whether email exists or not
    res_nonexistent = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@brightloop.test"},
        headers=headers,
    )
    assert res_nonexistent.status_code == 202
    assert "If an account exists" in res_nonexistent.json()["message"]


def test_password_reset_flow_and_session_revocation(client: TestClient, db):
    headers = get_csrf_context(client)
    email = "reset_target@brightloop.test"
    old_password = "Old@Password123"
    new_password = "BrandNew@Password123"

    user = User(
        email_normalized=email,
        name="Reset Subject",
        password_hash=hash_password(old_password),
        role="CUSTOMER",
        active=True,
    )
    db.add(user)
    db.commit()

    # Create an active session for this user
    active_session = UserSession(
        user_id=user.id,
        token_hash=hash_token("pre_existing_session_token"),
        csrf_hash=hash_token("csrf"),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(active_session)
    db.commit()

    # Trigger forgot-password
    with patch("app.services.auth.send_password_reset_email", return_value=True):
        res_req = client.post("/api/v1/auth/forgot-password", json={"email": email}, headers=headers)
    assert res_req.status_code == 202

    # Query the generated challenge
    challenge = db.scalar(
        select(AuthChallenge)
        .where(
            AuthChallenge.email_normalized == email,
            AuthChallenge.purpose == "RESET",
            AuthChallenge.consumed_at.is_(None),
        )
        .order_by(AuthChallenge.created_at.desc())
    )
    assert challenge is not None
    assert challenge.delivery_status == "SENT"
    assert challenge.delivery_attempts == 1

    # Synthesize raw token matching the challenge
    raw_token = "synthetic_reset_token_test_12345"
    challenge.token_hash = hash_token(raw_token)
    db.commit()

    # 1. Reset with invalid password complexity fails
    res_bad_pwd = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "weak"},
        headers=headers,
    )
    assert res_bad_pwd.status_code == 422

    # 2. Reset with valid password succeeds
    res_reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": new_password},
        headers=headers,
    )
    assert res_reset.status_code == 200

    # 3. User password hash must now verify with new password
    db.refresh(user)
    assert verify_password(new_password, user.password_hash)

    # 4. Old active session must now be revoked
    db.refresh(active_session)
    assert active_session.revoked_at is not None

    # 5. Token reuse must be rejected
    res_reused = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "Another@Password123"},
        headers=headers,
    )
    assert res_reused.status_code == 400


def test_password_reset_expired_token(client: TestClient, db):
    headers = get_csrf_context(client)
    email = "expired_reset@brightloop.test"
    user = User(
        email_normalized=email,
        name="Expired Target",
        password_hash=hash_password("Pass@12345"),
        role="CUSTOMER",
        active=True,
    )
    db.add(user)
    db.commit()

    raw_token = "expired_token_123456789"
    challenge = AuthChallenge(
        purpose="RESET",
        token_hash=hash_token(raw_token),
        email_normalized=email,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # expired
    )
    db.add(challenge)
    db.commit()

    res = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "Valid@Password123"},
        headers=headers,
    )
    assert res.status_code == 400


def test_smtp_failure_and_recovery_on_password_reset(client: TestClient, db):
    """
    When SMTP delivery fails during password reset:
    - Generic 202 response is still returned without leaking account existence or SMTP failure.
    - Safe delivery failure state is recorded in PostgreSQL (delivery_status = 'FAILED').
    - Subsequent retry with working SMTP recovers and records delivery_status = 'SENT'.
    """
    headers = get_csrf_context(client)
    email = "smtp_reset_fail@brightloop.test"
    user = User(
        email_normalized=email,
        name="SMTP Fail Subject",
        password_hash=hash_password("Valid@Pass123"),
        role="CUSTOMER",
        active=True,
    )
    db.add(user)
    db.commit()

    # 1. Simulate SMTP delivery failure
    with patch("app.services.auth.send_password_reset_email", return_value=False):
        res_fail = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": email},
            headers=headers,
        )
    # Must preserve generic forgot-password response without leaking failure or existence
    assert res_fail.status_code == 202
    assert "If an account exists" in res_fail.json()["message"]

    db.expire_all()
    failed_challenge = db.scalar(
        select(AuthChallenge)
        .where(
            AuthChallenge.email_normalized == email,
            AuthChallenge.purpose == "RESET",
            AuthChallenge.consumed_at.is_(None),
        )
        .order_by(AuthChallenge.created_at.desc())
    )
    assert failed_challenge is not None
    assert failed_challenge.delivery_status == "FAILED"
    assert failed_challenge.delivery_attempts == 1

    # 2. Simulate recovery with working SMTP
    with patch("app.services.auth.send_password_reset_email", return_value=True):
        res_recover = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": email},
            headers=headers,
        )
    assert res_recover.status_code == 202

    db.expire_all()
    recovered_challenge = db.scalar(
        select(AuthChallenge)
        .where(
            AuthChallenge.email_normalized == email,
            AuthChallenge.purpose == "RESET",
            AuthChallenge.consumed_at.is_(None),
        )
        .order_by(AuthChallenge.created_at.desc())
    )
    assert recovered_challenge is not None
    assert recovered_challenge.delivery_status == "SENT"
    assert recovered_challenge.delivery_attempts == 2


def test_smtp_failure_and_recovery_on_registration_linking(client: TestClient, db):
    """
    When SMTP delivery fails during registration linking:
    - Truthfully return 503 Service Unavailable (do not claim verification was sent).
    - Safe delivery failure state is recorded in PostgreSQL (delivery_status = 'FAILED').
    - Subsequent retry with working SMTP recovers, returns 202, and records delivery_status = 'SENT'.
    """
    headers = get_csrf_context(client)
    email = "smtp_reg_fail@brightloop.test"
    op_customer = Customer(
        name="SMTP Fail Corp",
        email_normalized=email,
        company="SMTP Fail Inc",
        user_id=None,
    )
    db.add(op_customer)
    db.commit()

    payload = {
        "name": "Linking Retrier",
        "email": email,
        "password": "Secure@Linking123",
    }

    # 1. Simulate SMTP delivery failure on registration
    with patch("app.services.auth.send_customer_verification_email", return_value=False):
        res_fail = client.post("/api/v1/auth/register", json=payload, headers=headers)

    # Must NOT claim email was sent: return 503
    assert res_fail.status_code == 503
    assert "Verification email delivery failed" in res_fail.json()["error"]["message"]

    db.expire_all()
    failed_challenge = db.scalar(
        select(AuthChallenge)
        .where(
            AuthChallenge.email_normalized == email,
            AuthChallenge.purpose == "LINK_SIGNUP",
            AuthChallenge.consumed_at.is_(None),
        )
        .order_by(AuthChallenge.created_at.desc())
    )
    assert failed_challenge is not None
    assert failed_challenge.delivery_status == "FAILED"
    assert failed_challenge.delivery_attempts == 1

    # 2. Simulate recovery with working SMTP
    with patch("app.services.auth.send_customer_verification_email", return_value=True):
        res_recover = client.post("/api/v1/auth/register", json=payload, headers=headers)

    assert res_recover.status_code == 202
    assert res_recover.json()["requires_verification"] is True

    db.expire_all()
    recovered_challenge = db.scalar(
        select(AuthChallenge)
        .where(
            AuthChallenge.email_normalized == email,
            AuthChallenge.purpose == "LINK_SIGNUP",
            AuthChallenge.consumed_at.is_(None),
        )
        .order_by(AuthChallenge.created_at.desc())
    )
    assert recovered_challenge is not None
    assert recovered_challenge.delivery_status == "SENT"
    assert recovered_challenge.delivery_attempts == 2
