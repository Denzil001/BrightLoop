import collections
from datetime import datetime, timezone, timedelta
import logging
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import select, update
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
from app.models.users import AuthChallenge, Session as UserSession, User
from app.services.email import send_customer_verification_email, send_password_reset_email

logger = logging.getLogger(__name__)

# In-memory sliding window rate limiter
# Key: (action, identifier) -> deque of timestamps
_rate_limits = collections.defaultdict(collections.deque)


def check_rate_limit(
    action: str, identifier: str, max_attempts: int, window_seconds: int
) -> None:
    """Enforce rate limits per action and identifier (IP or email). Raises 429 if exceeded."""
    now = datetime.now(timezone.utc)
    key = f"{action}:{identifier}"
    attempts = _rate_limits[key]

    # Purge attempts outside window
    cutoff = now - timedelta(seconds=window_seconds)
    while attempts and attempts[0] < cutoff:
        attempts.popleft()

    if len(attempts) >= max_attempts:
        retry_after = int((attempts[0] + timedelta(seconds=window_seconds) - now).total_seconds())
        retry_after = max(1, retry_after)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    attempts.append(now)


def record_failed_attempt(action: str, identifier: str) -> None:
    now = datetime.now(timezone.utc)
    key = f"{action}:{identifier}"
    _rate_limits[key].append(now)


def clear_failed_attempts(action: str, identifier: str) -> None:
    key = f"{action}:{identifier}"
    if key in _rate_limits:
        _rate_limits[key].clear()


def create_user_session(
    db: DbSession, user: User
) -> Tuple[UserSession, str, str]:
    """
    Create a new active session for the user with hashed session and CSRF tokens.
    Returns (session_model, raw_session_token, raw_csrf_token).
    """
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
    db.commit()
    db.refresh(session)
    return session, raw_session_token, raw_csrf_token


def revoke_session(db: DbSession, session_token: str) -> None:
    token_h = hash_token(session_token)
    now = datetime.now(timezone.utc)
    db.execute(
        update(UserSession)
        .where(UserSession.token_hash == token_h, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
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

    # Validate password complexity
    valid, err_msg = validate_password_complexity(password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err_msg)

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
        # Existing unlinked customer: create LINK_SIGNUP challenge and send email
        raw_token = generate_secure_token(32)
        challenge = AuthChallenge(
            purpose="LINK_SIGNUP",
            token_hash=hash_token(raw_token),
            email_normalized=email_norm,
            customer_id=existing_customer.id,
            pending_password_hash=hash_password(password),
            pending_name=name,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(challenge)
        db.commit()

        # Send verification link
        send_customer_verification_email(email_norm, name, raw_token)
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
        challenge = AuthChallenge(
            purpose="RESET",
            token_hash=hash_token(raw_token),
            email_normalized=email_norm,
            user_id=user.id,
            expires_at=now + timedelta(minutes=30),
        )
        db.add(challenge)
        db.commit()
        send_password_reset_email(email_norm, user.name, raw_token)


def reset_password(db: DbSession, raw_token: str, new_password: str) -> None:
    """Validates reset token, sets new password, and revokes all active sessions."""
    valid, err_msg = validate_password_complexity(new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err_msg)

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

    # Revoke all existing sessions for this user
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
