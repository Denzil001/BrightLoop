from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.api.contracts import created_location
from app.api.deps import (
    get_current_db,
    get_current_session,
    get_current_user,
    get_session_token_from_request,
    verify_csrf,
    verify_origin,
    verify_preauth_csrf,
)
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
from app.schemas.auth import (
    ChangePasswordRequest,
    CsrfResponse,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    UserDTO,
    VerifySignupRequest,
)
from app.services.auth import (
    check_rate_limit,
    create_user_session,
    register_customer_flow,
    request_password_reset,
    reset_password,
    revoke_all_user_sessions,
    revoke_session,
    verify_signup_challenge,
)

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: Request,
    payload: RegisterRequest,
    response: Response,
    db: Session = Depends(get_current_db),
    _: None = Depends(verify_origin),
    __: str = Depends(verify_preauth_csrf),
):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit("register", client_ip, max_attempts=10, window_seconds=300, db=db)

    verified, message, user = register_customer_flow(
        db=db,
        name=payload.name,
        email=payload.email,
        password=payload.password,
        company=payload.company,
    )

    if not verified:
        response.status_code = status.HTTP_202_ACCEPTED
        return RegisterResponse(message=message, requires_verification=True, user=None)

    customer = db.scalar(select(Customer).where(Customer.user_id == user.id))
    user_dto = UserDTO(
        id=user.id,
        email=user.email_normalized,
        name=user.name,
        role=user.role,
        active=user.active,
        customer_id=customer.id if customer else None,
    )
    created_location(response, "auth/me")
    return RegisterResponse(message=message, requires_verification=False, user=user_dto)


@router.post("/verify-signup", status_code=status.HTTP_200_OK)
def verify_signup(
    request: Request,
    payload: VerifySignupRequest,
    db: Session = Depends(get_current_db),
    _: None = Depends(verify_origin),
    __: str = Depends(verify_preauth_csrf),
):
    check_rate_limit("verify_signup", request.client.host if request.client else "unknown", 10, 300, db)
    user = verify_signup_challenge(db, payload.token)
    return {"message": "Account verified and linked successfully. Please sign in.", "email": user.email_normalized}


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_current_db),
    _: None = Depends(verify_origin),
    csrf_token: str = Depends(verify_preauth_csrf),
):
    client_ip = request.client.host if request.client else "unknown"
    email_norm = normalize_email(payload.email)

    check_rate_limit("login", client_ip, max_attempts=15, window_seconds=300, db=db)
    check_rate_limit("login_account", email_norm, max_attempts=10, window_seconds=300, db=db)

    user = db.scalar(select(User).where(User.email_normalized == email_norm))
    if not user or not verify_password(payload.password, user.password_hash):
        db.add(AuditEvent(action="AUTH_LOGIN_FAILED", target_type="authentication",
            target_id=hash_token(email_norm), payload={}))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deactivated. Please contact an administrator.",
        )


    verified_password_hash = user.password_hash
    # Consume the pre-auth CSRF challenge if present
    token_h = hash_token(csrf_token)
    preauth = db.scalar(
        select(AuthChallenge).where(
            AuthChallenge.token_hash == token_h,
            AuthChallenge.purpose == "PREAUTH_CSRF",
            AuthChallenge.consumed_at.is_(None),
        )
    )
    if preauth:
        preauth.consumed_at = datetime.now(timezone.utc)
        db.commit()

    # Create new session with rotated CSRF token
    session_record, raw_session_token, raw_csrf_token = create_user_session(db, user, expected_password_hash=verified_password_hash)

    settings = get_settings()
    is_prod = settings.APP_ENV == "production"

    # Set HttpOnly session cookie
    response.set_cookie(
        key="brightloop_session",
        value=raw_session_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        path="/",
    )

    # Set readable CSRF cookie so frontend clients can echo it in X-CSRF-Token header
    response.set_cookie(
        key="brightloop_csrf",
        value=raw_csrf_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=False,
        samesite="lax",
        secure=is_prod,
        path="/",
    )

    response.headers["X-CSRF-Token"] = raw_csrf_token

    customer = db.scalar(select(Customer).where(Customer.user_id == user.id)) if user.role == "CUSTOMER" else None

    user_dto = UserDTO(
        id=user.id,
        email=user.email_normalized,
        name=user.name,
        role=user.role,
        active=user.active,
        customer_id=customer.id if customer else None,
    )

    return LoginResponse(user=user_dto, csrf_token=raw_csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_current_db),
    user_session: UserSession = Depends(get_current_session),
    _: None = Depends(verify_csrf),
    __: None = Depends(verify_origin),
):
    raw_token = get_session_token_from_request(request)
    revoke_session(db, raw_token)

    response.delete_cookie("brightloop_session", path="/")
    response.delete_cookie("brightloop_csrf", path="/")
    return None


@router.get("/me", response_model=UserDTO)
def get_me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_current_db),
):
    customer = db.scalar(select(Customer).where(Customer.user_id == user.id)) if user.role == "CUSTOMER" else None
    return UserDTO(
        id=user.id,
        email=user.email_normalized,
        name=user.name,
        role=user.role,
        active=user.active,
        customer_id=customer.id if customer else None,
    )


@router.get("/csrf", response_model=CsrfResponse)
def get_csrf(
    request: Request,
    response: Response,
    db: Session = Depends(get_current_db),
):
    token = request.cookies.get("brightloop_csrf")
    now = datetime.now(timezone.utc)
    valid_token = None

    if token:
        token_h = hash_token(token)
        preauth = db.scalar(
            select(AuthChallenge).where(
                AuthChallenge.token_hash == token_h,
                AuthChallenge.purpose == "PREAUTH_CSRF",
                AuthChallenge.consumed_at.is_(None),
                AuthChallenge.expires_at > now,
            )
        )
        if preauth:
            valid_token = token
        else:
            session = db.scalar(
                select(UserSession).where(
                    UserSession.csrf_hash == token_h,
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > now,
                )
            )
            if session:
                valid_token = token

    if not valid_token:
        check_rate_limit("csrf_issue", request.client.host if request.client else "unknown", 60, 60, db)
        valid_token = generate_secure_token(32)
        challenge = AuthChallenge(
            purpose="PREAUTH_CSRF",
            token_hash=hash_token(valid_token),
            expires_at=now + timedelta(hours=12),
        )
        db.add(challenge)
        db.commit()

        settings = get_settings()
        response.set_cookie(
            key="brightloop_csrf",
            value=valid_token,
            max_age=43200,
            httponly=False,
            samesite="lax",
            secure=settings.APP_ENV == "production",
            path="/",
        )

    response.headers["X-CSRF-Token"] = valid_token
    return CsrfResponse(csrf_token=valid_token)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_current_db),
    _: None = Depends(verify_origin),
    __: str = Depends(verify_preauth_csrf),
):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit("forgot_pwd", client_ip, max_attempts=5, window_seconds=300, db=db)

    request_password_reset(db, payload.email)
    return {
        "message": "If an account exists with that email, a password reset link has been sent."
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password_endpoint(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_current_db),
    _: None = Depends(verify_origin),
    __: str = Depends(verify_preauth_csrf),
):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit("reset_pwd", client_ip, max_attempts=10, window_seconds=300, db=db)

    reset_password(db, payload.token, payload.new_password)
    return {"message": "Password has been reset successfully. Please sign in with your new password."}


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_current_db),
    user: User = Depends(get_current_user),
    user_session: UserSession = Depends(get_current_session),
    _: None = Depends(verify_csrf),
    __: None = Depends(verify_origin),
):
    user = db.scalar(select(User).where(User.id == user.id).with_for_update()
                     .execution_options(populate_existing=True))
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    valid, err_msg = validate_password_complexity(payload.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=err_msg)

    user.password_hash = hash_password(payload.new_password)
    user.version += 1
    db.add(AuditEvent(actor_id=user.id, action="AUTH_PASSWORD_CHANGED", target_type="user", target_id=str(user.id), payload={}))
    # Commit password change and revocation atomically under the session-creation lock.
    db.execute(update(UserSession).where(UserSession.user_id == user.id,
        UserSession.revoked_at.is_(None), UserSession.token_hash != user_session.token_hash)
        .values(revoked_at=datetime.now(timezone.utc)))
    db.commit()
    return {"message": "Password changed successfully. Other sessions have been signed out."}
