from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.core.security import hash_password, hash_token, verify_password
from app.models.users import AuthChallenge, Session as UserSession, User


def test_forgot_password_generic_acceptance(client: TestClient):
    # Tests that /forgot-password always returns 202 whether email exists or not
    res_nonexistent = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@brightloop.test"})
    assert res_nonexistent.status_code == 202
    assert "If an account exists" in res_nonexistent.json()["message"]


def test_password_reset_flow_and_session_revocation(client: TestClient, db):
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
    res_req = client.post("/api/v1/auth/forgot-password", json={"email": email})
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

    # Synthesize raw token matching the challenge
    raw_token = "synthetic_reset_token_test_12345"
    challenge.token_hash = hash_token(raw_token)
    db.commit()

    # 1. Reset with invalid password complexity fails
    res_bad_pwd = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "weak"},
    )
    assert res_bad_pwd.status_code == 422

    # 2. Reset with valid password succeeds
    res_reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": new_password},
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
    )
    assert res_reused.status_code == 400


def test_password_reset_expired_token(client: TestClient, db):
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
    )
    assert res.status_code == 400
