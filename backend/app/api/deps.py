from datetime import datetime, timezone
import uuid
from typing import Generator, List, Optional
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import Settings, get_settings
from app.core.security import hash_token
from app.db.session import get_db
from app.models.customers import Customer
from app.models.users import Session as UserSession, User


def get_current_db() -> Generator[Session, None, None]:
    yield from get_db()


def get_app_settings() -> Settings:
    return get_settings()


def get_session_token_from_request(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> str:
    """Extract session token from HttpOnly cookie or Authorization Bearer header."""
    cookie_token = request.cookies.get("brightloop_session")
    if cookie_token:
        return cookie_token

    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials were not provided.",
    )


def get_current_session(
    request: Request,
    db: Session = Depends(get_current_db),
    authorization: Optional[str] = Header(None),
) -> UserSession:
    """Validate active, unexpired, unrevoked user session."""
    token = None
    cookie_token = request.cookies.get("brightloop_session")
    if cookie_token:
        token = cookie_token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
        )

    token_h = hash_token(token)
    now = datetime.now(timezone.utc)

    user_session = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == token_h,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )

    if not user_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or been revoked. Please sign in again.",
        )

    return user_session


def get_current_user(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_current_db),
) -> User:
    """Retrieve the user associated with the active session."""
    user = db.scalar(select(User).where(User.id == session.user_id))
    if not user or not user.active:
        now = datetime.now(timezone.utc)
        session.revoked_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found.",
        )
    return user


def require_role(allowed_roles: List[str]):
    """Enforce role-based access control (RBAC)."""

    def role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role {user.role}.",
            )
        return user

    return role_checker


def get_current_customer(
    user: User = Depends(require_role(["CUSTOMER"])),
    db: Session = Depends(get_current_db),
) -> Customer:
    """Retrieve customer record for currently authenticated customer."""
    customer = db.scalar(select(Customer).where(Customer.user_id == user.id))
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer record not associated with this account.",
        )
    return customer


def verify_csrf(
    request: Request,
    session: UserSession = Depends(get_current_session),
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
) -> None:
    """Verify CSRF token for state-changing HTTP methods on authenticated routes."""
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        if not x_csrf_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing CSRF token header (X-CSRF-Token).",
            )
        token_h = hash_token(x_csrf_token)
        if token_h != session.csrf_hash:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token.",
            )
