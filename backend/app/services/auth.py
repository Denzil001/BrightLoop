from datetime import datetime, timezone, timedelta
import logging
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from app.models.rate_limits import RateLimitWindow
from sqlalchemy.orm import Session as DbSession
from app.core.config import get_settings
from app.core.security import (
    generate_secure_token,
    hash_password,
    hash_token,
    normalize_email,
    validate_password_complexity,
    verify_password,
)
from app.models.customers import Customer
from app.models.audit import AuditEvent
from app.models.users import AuthChallenge, Session as UserSession, User
from app.services.email import send_customer_verification_email, send_password_reset_email

logger = logging.getLogger(__name__)

def check_rate_limit(action: str, identifier: str, max_attempts: int, window_seconds: int, db: DbSession) -> None:
    """Persist exactly one attempt under a per-key row lock, across API workers.

    Call before domain writes: this deliberately commits attempt accounting even
    when subsequent authentication fails. Store hashed keys, never raw emails/IPs.
    A successful login does not erase the IP/account abuse window.
    """
    now = datetime.now(timezone.utc)
    key = hash_token(f"{action}:{identifier}")
    db.execute(insert(RateLimitWindow).values(key_hash=key, attempts=[], updated_at=now)
               .on_conflict_do_nothing(index_elements=[RateLimitWindow.key_hash]))
    window = db.scalar(select(RateLimitWindow).where(RateLimitWindow.key_hash == key)
                       .with_for_update().execution_options(populate_existing=True))
    cutoff = now.timestamp() - window_seconds
    attempts = [stamp for stamp in window.attempts if stamp > cutoff]
    blocked = len(attempts) >= max_attempts
    retry_after = max(1, int(attempts[0] + window_seconds - now.timestamp()) + 1) if blocked else None
    if not blocked:
        attempts.append(now.timestamp())
    window.attempts, window.updated_at = attempts, now
    db.commit()
    if blocked:
        raise HTTPException(status_code=429,
            detail=f"Too many attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)})


def create_user_session(
    db: DbSession, user: User, expected_password_hash: str | None = None
) -> Tuple[UserSession, str, str]:
    """
    Create a new active session for the user with hashed session and CSRF tokens.
    Returns (session_model, raw_session_token, raw_csrf_token).
    """
    # Serialize session creation with credential changes and deactivation.
    user = db.scalar(select(User).where(User.id == user.id).with_for_update()
                     .execution_options(populate_existing=True))
    if not user or not user.active or (expected_password_hash is not None and user.password_hash != expected_password_hash):
        raise HTTPException(status_code=401, detail="Account credentials changed. Please sign in again.")
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)

    raw_session_token = generate_secure_token(32)
    raw_csrf_token = generate_secure_token(32)

    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(raw_session_token),
        csrf_hash=hash_token(raw_csrf_token),
        expires_at=expires_at,
        created_at=now,
    )
    db.add(session)
    db.add(AuditEvent(actor_id=user.id, action="AUTH_LOGIN", target_type="user", target_id=str(user.id), payload={}))
    db.commit()
    db.refresh(session)
    return session, raw_session_token, raw_csrf_token


def revoke_session(db: DbSession, session_token: str) -> None:
    token_h = hash_token(session_token)
    now = datetime.now(timezone.utc)
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_h))
    db.execute(
        update(UserSession)
        .where(UserSession.token_hash == token_h, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    if session:
        db.add(AuditEvent(actor_id=session.user_id, action="AUTH_LOGOUT", target_type="user", target_id=str(session.user_id), payload={}))
    db.commit()


def revoke_all_user_sessions(
    db: DbSession, user_id, except_token_hash: Optional[str] = None
) -> None:
    now = datetime.now(timezone.utc)
    stmt = update(UserSession).where(
        UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
    )
    if except_token_hash:
        stmt = stmt.where(UserSession.token_hash != except_token_hash)
    stmt = stmt.values(revoked_at=now)
    db.execute(stmt)
    db.commit()


def register_customer_flow(
    db: DbSession,
    name: str,
    email: str,
    password: str,
    company: Optional[str] = None,
) -> Tuple[bool, str, Optional[User]]:
    """
    Handles atomic registration vs verified linking for an unlinked operational customer.
    Returns (verified: bool, message: str, user: Optional[User]).
    """
    email_norm = normalize_email(email)
    now = datetime.now(timezone.utc)

    # Validate password complexity
    valid, err_msg = validate_password_complexity(password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=err_msg)

    # Check if a User already exists with this email
    existing_user = db.scalar(select(User).where(User.email_normalized == email_norm))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # Check if an operational Customer already exists
    existing_customer = db.scalar(
        select(Customer).where(Customer.email_normalized == email_norm).with_for_update()
    )

    if existing_customer:
        if existing_customer.user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists.",
            )
        # Existing unlinked customer: create or update LINK_SIGNUP challenge and send email
        raw_token = generate_secure_token(32)
        existing_challenge = db.scalar(
            select(AuthChallenge)
            .where(
                AuthChallenge.customer_id == existing_customer.id,
                AuthChallenge.purpose == "LINK_SIGNUP",
                AuthChallenge.consumed_at.is_(None),
                AuthChallenge.expires_at > now,
            )
            .with_for_update()
        )

        if existing_challenge:
            challenge = existing_challenge
            challenge.token_hash = hash_token(raw_token)
            challenge.pending_password_hash = hash_password(password)
            challenge.pending_name = name
            challenge.expires_at = now + timedelta(hours=24)
            challenge.delivery_attempts += 1
            challenge.delivery_status = "PENDING"
        else:
            challenge = AuthChallenge(
                purpose="LINK_SIGNUP",
                token_hash=hash_token(raw_token),
                email_normalized=email_norm,
                customer_id=existing_customer.id,
                pending_password_hash=hash_password(password),
                pending_name=name,
                expires_at=now + timedelta(hours=24),
                delivery_status="PENDING",
                delivery_attempts=1,
            )
            db.add(challenge)

        db.flush()

        # Send verification link
        sent = send_customer_verification_email(email_norm, name, raw_token)
        if not sent:
            challenge.delivery_status = "FAILED"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Verification email delivery failed. Please try again later.",
            )

        challenge.delivery_status = "SENT"
        db.commit()
        return (
            False,
            "An existing customer profile was found with this email. A verification link has been sent to complete linking your account.",
            None,
        )

    # No existing customer: atomic creation of User and Customer
    pwd_hash = hash_password(password)
    new_user = User(
        email_normalized=email_norm,
        name=name,
        password_hash=pwd_hash,
        role="CUSTOMER",
        active=True,
    )
    db.add(new_user)
    db.flush()

    new_customer = Customer(
        user_id=new_user.id,
        email_normalized=email_norm,
        name=name,
        company=company,
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_user)

    return True, "Account registered successfully.", new_user


def verify_signup_challenge(db: DbSession, raw_token: str) -> User:
    """Consumes LINK_SIGNUP challenge token and creates User linked to existing Customer."""
    token_h = hash_token(raw_token)
    now = datetime.now(timezone.utc)

    challenge = db.scalar(
        select(AuthChallenge)
        .where(
            AuthChallenge.token_hash == token_h,
            AuthChallenge.purpose == "LINK_SIGNUP",
            AuthChallenge.consumed_at.is_(None),
            AuthChallenge.expires_at > now,
        )
        .with_for_update()
    )

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used verification token.",
        )

    customer = db.scalar(
        select(Customer)
        .where(Customer.id == challenge.customer_id)
        .with_for_update()
    )
    if not customer or customer.user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This customer record has already been linked or is unavailable.",
        )

    # Double-check email conflict
    if db.scalar(select(User).where(User.email_normalized == challenge.email_normalized)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    new_user = User(
        email_normalized=challenge.email_normalized,
        name=challenge.pending_name or customer.name,
        password_hash=challenge.pending_password_hash,
        role="CUSTOMER",
        active=True,
    )
    db.add(new_user)
    db.flush()

    customer.user_id = new_user.id
    customer.version += 1
    challenge.consumed_at = now
    db.commit()
    db.refresh(new_user)
    return new_user


def request_password_reset(db: DbSession, email: str) -> None:
    """Generates a single-use 30-minute reset token and sends it via email without leaking user existence."""
    email_norm = normalize_email(email)
    now = datetime.now(timezone.utc)

    user = db.scalar(select(User).where(User.email_normalized == email_norm, User.active.is_(True)))
    if user:
        raw_token = generate_secure_token(32)
        existing_challenge = db.scalar(
            select(AuthChallenge)
            .where(
                AuthChallenge.user_id == user.id,
                AuthChallenge.purpose == "RESET",
                AuthChallenge.consumed_at.is_(None),
                AuthChallenge.expires_at > now,
            )
            .with_for_update()
        )

        if existing_challenge:
            challenge = existing_challenge
            challenge.token_hash = hash_token(raw_token)
            challenge.expires_at = now + timedelta(minutes=30)
            challenge.delivery_attempts += 1
            challenge.delivery_status = "PENDING"
        else:
            challenge = AuthChallenge(
                purpose="RESET",
                token_hash=hash_token(raw_token),
                email_normalized=email_norm,
                user_id=user.id,
                expires_at=now + timedelta(minutes=30),
                delivery_status="PENDING",
                delivery_attempts=1,
            )
            db.add(challenge)

        db.flush()
        sent = send_password_reset_email(email_norm, user.name, raw_token)
        if sent:
            challenge.delivery_status = "SENT"
        else:
            challenge.delivery_status = "FAILED"
        db.commit()


def reset_password(db: DbSession, raw_token: str, new_password: str) -> None:
    """Validates reset token, sets new password, and revokes all active sessions."""
    valid, err_msg = validate_password_complexity(new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=err_msg)

    token_h = hash_token(raw_token)
    now = datetime.now(timezone.utc)

    challenge = db.scalar(
        select(AuthChallenge)
        .where(
            AuthChallenge.token_hash == token_h,
            AuthChallenge.purpose == "RESET",
            AuthChallenge.consumed_at.is_(None),
            AuthChallenge.expires_at > now,
        )
        .with_for_update()
    )

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired, or already used password reset link. Please request a new one.",
        )

    user = db.scalar(select(User).where(User.id == challenge.user_id).with_for_update())
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    user.password_hash = hash_password(new_password)
    user.version += 1
    challenge.consumed_at = now
    db.add(AuditEvent(actor_id=user.id, action="AUTH_PASSWORD_RESET", target_type="user", target_id=str(user.id), payload={}))

    # Revoke all existing sessions for this user
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
