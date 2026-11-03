from datetime import datetime, timezone
from urllib.parse import urlparse
import uuid
from typing import Generator, List, Optional
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.config import Settings, get_settings
from app.core.security import hash_token
from app.db.session import get_db
from app.models.customers import Customer
from app.models.users import AuthChallenge, Session as UserSession, User


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


def verify_origin(request: Request) -> None:
    """
    Validate that request's Origin header (or Referer) matches configured allowed frontend origins.
    Enforces server-side cross-origin request protection independent of CORS preflight.
    """
    origin = request.headers.get("origin")
    if not origin:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                origin = f"{parsed.scheme}://{parsed.netloc}"

    if origin:
        settings = get_settings()
        allowed = [
            o.strip().rstrip("/")
            for o in settings.FRONTEND_ORIGIN.split(",")
            if o.strip()
        ]
        if origin.rstrip("/") not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Disallowed cross-origin request from '{origin}'.",
            )


def verify_csrf(
    request: Request,
    session: UserSession = Depends(get_current_session),
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
    _origin: None = Depends(verify_origin),
) -> None:
    """Apply one consistent Origin and session-bound CSRF policy to protected writes."""
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        if not x_csrf_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing CSRF token header (X-CSRF-Token).",
            )
        cookie_csrf = request.cookies.get("brightloop_csrf")
        if cookie_csrf and cookie_csrf != x_csrf_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token header does not match cookie.",
            )
        token_h = hash_token(x_csrf_token)
        if token_h != session.csrf_hash:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token.",
            )


def verify_preauth_csrf(
    request: Request,
    db: Session = Depends(get_current_db),
    x_csrf_token: Optional[str] = Header(None, alias="X-CSRF-Token"),
) -> str:
    """
    Validate pre-auth CSRF token for public mutations (login, register, reset, etc.).
    Requires X-CSRF-Token header bound to a PREAUTH_CSRF challenge or active session.
    """
    token = x_csrf_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing CSRF token header (X-CSRF-Token).",
        )

    cookie_csrf = request.cookies.get("brightloop_csrf")
    if cookie_csrf and cookie_csrf != token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token header does not match cookie.",
        )

    token_h = hash_token(token)
    now = datetime.now(timezone.utc)

    # 1. Check unconsumed pre-auth challenge in PostgreSQL
    challenge = db.scalar(
        select(AuthChallenge).where(
            AuthChallenge.token_hash == token_h,
            AuthChallenge.purpose == "PREAUTH_CSRF",
            AuthChallenge.consumed_at.is_(None),
            AuthChallenge.expires_at > now,
        )
    )
    if challenge:
        return token

    # 2. Check active user session (if client was already authenticated)
    session = db.scalar(
        select(UserSession).where(
            UserSession.csrf_hash == token_h,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
    )
    if session:
        return token

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid or expired CSRF token.",
    )
