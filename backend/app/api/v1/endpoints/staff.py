from datetime import datetime, timezone
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from app.api.deps import (
    get_current_db,
    get_current_user,
    require_role,
    verify_csrf,
)
from app.core.security import (
    hash_password,
    normalize_email,
    validate_password_complexity,
)
from app.models.users import Session as UserSession, User
from app.schemas.staff import StaffCreate, StaffListResponse, StaffResponse, StaffUpdate

router = APIRouter()


@router.get("", response_model=StaffListResponse)
def list_staff(
    search: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    query = select(User).where(User.role == "STAFF")

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.where(
            (func.lower(User.name).like(search_term))
            | (User.email_normalized.like(search_term))
        )

    if active is not None:
        query = query.where(User.active == active)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    items_query = (
        query.order_by(User.created_at.desc(), User.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = db.scalars(items_query).all()

    items = [
        StaffResponse(
            id=u.id,
            name=u.name,
            email=u.email_normalized,
            role=u.role,
            active=u.active,
            version=u.version,
            created_at=u.created_at,
            updated_at=u.updated_at,
        )
        for u in users
    ]

    return StaffListResponse(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
    __: None = Depends(verify_csrf),
):
    email_norm = normalize_email(payload.email)

    valid, err_msg = validate_password_complexity(payload.initial_password)
    if not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=err_msg)

    existing_user = db.scalar(select(User).where(User.email_normalized == email_norm))
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    user = User(
        email_normalized=email_norm,
        name=payload.name,
        password_hash=hash_password(payload.initial_password),
        role="STAFF",
        active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return StaffResponse(
        id=user.id,
        name=user.name,
        email=user.email_normalized,
        role=user.role,
        active=user.active,
        version=user.version,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.patch("/{staff_id}", response_model=StaffResponse)
def update_staff(
    staff_id: uuid.UUID,
    payload: StaffUpdate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
    __: None = Depends(verify_csrf),
):
    user = db.scalar(select(User).where(User.id == staff_id, User.role == "STAFF"))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

    if payload.expected_version is not None and user.version != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Staff record has been modified by another operation. Please refresh and retry.",
        )

    if payload.name is not None:
        user.name = payload.name.strip()
        user.version += 1

    db.commit()
    db.refresh(user)

    return StaffResponse(
        id=user.id,
        name=user.name,
        email=user.email_normalized,
        role=user.role,
        active=user.active,
        version=user.version,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.post("/{staff_id}/deactivate", status_code=status.HTTP_200_OK)
def deactivate_staff(
    staff_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    current_admin: User = Depends(require_role(["ADMIN"])),
    _: None = Depends(verify_csrf),
):
    if staff_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    user = db.scalar(select(User).where(User.id == staff_id, User.role == "STAFF"))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

    user.active = False
    user.version += 1

    # Immediately revoke all active sessions for this user
    now = datetime.now(timezone.utc)
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()

    return {"message": "Staff member deactivated and active sessions revoked."}


@router.post("/{staff_id}/reactivate", status_code=status.HTTP_200_OK)
def reactivate_staff(
    staff_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
    __: None = Depends(verify_csrf),
):
    user = db.scalar(select(User).where(User.id == staff_id, User.role == "STAFF"))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")

    user.active = True
    user.version += 1
    db.commit()

    return {"message": "Staff member reactivated."}
