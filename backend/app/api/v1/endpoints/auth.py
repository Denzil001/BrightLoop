from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import (
    get_current_db,
    get_current_session,
    get_current_user,
    get_session_token_from_request,
    verify_csrf,
)
from app.core.config import get_settings
from app.core.security import (
    hash_password,
    hash_token,
    normalize_email,
    validate_password_complexity,
    verify_password,
)
from app.models.customers import Customer
from app.models.users import Session as UserSession, User
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
    clear_failed_attempts,
    create_user_session,
    record_failed_attempt,
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
):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit("register", client_ip, max_attempts=10, window_seconds=300)

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
    return RegisterResponse(message=message, requires_verification=False, user=user_dto)


@router.post("/verify-signup", status_code=status.HTTP_200_OK)
def verify_signup(
    payload: VerifySignupRequest,
    db: Session = Depends(get_current_db),
):
    user = verify_signup_challenge(db, payload.token)
    return {"message": "Account verified and linked successfully. Please sign in.", "email": user.email_normalized}


@router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_current_db),
):
    client_ip = request.client.host if request.client else "unknown"
    email_norm = normalize_email(payload.email)

    check_rate_limit("login", client_ip, max_attempts=15, window_seconds=300)
    check_rate_limit("login_account", email_norm, max_attempts=10, window_seconds=300)

    user = db.scalar(select(User).where(User.email_normalized == email_norm))
    if not user or not verify_password(payload.password, user.password_hash):
        record_failed_attempt("login", client_ip)
        record_failed_attempt("login_account", email_norm)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account has been deactivated. Please contact an administrator.",
        )

    clear_failed_attempts("login", client_ip)
    clear_failed_attempts("login_account", email_norm)

    session_record, raw_session_token, raw_csrf_token = create_user_session(db, user)

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
):
    token = request.cookies.get("brightloop_csrf")
    if not token:
        token = generate_secure_token(32)
        response.set_cookie(
            key="brightloop_csrf",
            value=token,
            max_age=43200,
            httponly=False,
            samesite="lax",
            secure=get_settings().APP_ENV == "production",
            path="/",
        )
    return CsrfResponse(csrf_token=token)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_current_db),
):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit("forgot_pwd", client_ip, max_attempts=5, window_seconds=300)

    request_password_reset(db, payload.email)
    return {
        "message": "If an account exists with that email, a password reset link has been sent."
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password_endpoint(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_current_db),
):
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit("reset_pwd", client_ip, max_attempts=10, window_seconds=300)

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
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    valid, err_msg = validate_password_complexity(payload.new_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err_msg)

    user.password_hash = hash_password(payload.new_password)
    user.version += 1
    db.commit()

    # Revoke other sessions while keeping current session
    revoke_all_user_sessions(db, user.id, except_token_hash=user_session.token_hash)
    return {"message": "Password changed successfully. Other sessions have been signed out."}
