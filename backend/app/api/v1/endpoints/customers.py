import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.api.deps import (
    get_current_db,
    get_current_user,
    require_role,
    verify_csrf,
)
from app.core.security import normalize_email
from app.models.customers import Customer
from app.models.users import User
from app.schemas.customers import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
)

router = APIRouter()


def _to_customer_response(c: Customer) -> CustomerResponse:
    return CustomerResponse(
        id=c.id,
        name=c.name,
        email=c.email_normalized,
        company=c.company,
        phone=c.phone,
        billing_address_line1=c.billing_address_line1,
        billing_address_line2=c.billing_address_line2,
        billing_city=c.billing_city,
        billing_state=c.billing_state,
        billing_postal_code=c.billing_postal_code,
        billing_country=c.billing_country,
        user_id=c.user_id,
        has_portal_login=c.user_id is not None,
        version=c.version,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=CustomerListResponse)
def list_customers(
    search: Optional[str] = Query(None),
    portal_status: Optional[str] = Query(None, pattern="^(linked|unlinked)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN", "STAFF"])),
):
    query = select(Customer)

    if search:
        term = f"%{search.strip().lower()}%"
        query = query.where(
            (func.lower(Customer.name).like(term))
            | (func.lower(Customer.company).like(term))
            | (Customer.email_normalized.like(term))
        )

    if portal_status == "linked":
        query = query.where(Customer.user_id.is_not(None))
    elif portal_status == "unlinked":
        query = query.where(Customer.user_id.is_(None))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    items_query = (
        query.order_by(Customer.created_at.desc(), Customer.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    customers = db.scalars(items_query).all()

    return CustomerListResponse(
        items=[_to_customer_response(c) for c in customers],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN", "STAFF"])),
    __: None = Depends(verify_csrf),
):
    email_norm = normalize_email(payload.email)

    existing = db.scalar(select(Customer).where(Customer.email_normalized == email_norm))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A customer record with this email already exists.",
        )

    customer = Customer(
        name=payload.name.strip(),
        email_normalized=email_norm,
        company=payload.company.strip() if payload.company else None,
        phone=payload.phone.strip() if payload.phone else None,
        billing_address_line1=payload.billing_address_line1.strip() if payload.billing_address_line1 else None,
        billing_address_line2=payload.billing_address_line2.strip() if payload.billing_address_line2 else None,
        billing_city=payload.billing_city.strip() if payload.billing_city else None,
        billing_state=payload.billing_state.strip() if payload.billing_state else None,
        billing_postal_code=payload.billing_postal_code.strip() if payload.billing_postal_code else None,
        billing_country=payload.billing_country.strip() if payload.billing_country else None,
        user_id=None,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    return _to_customer_response(customer)


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN", "STAFF"])),
):
    customer = db.scalar(select(Customer).where(Customer.id == customer_id))
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return _to_customer_response(customer)


@router.patch("/{customer_id}", response_model=CustomerResponse)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN", "STAFF"])),
    __: None = Depends(verify_csrf),
):
    customer = db.scalar(select(Customer).where(Customer.id == customer_id))
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    if payload.expected_version is not None and customer.version != payload.expected_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer record has been modified by another operation. Please refresh and retry.",
        )

    if payload.name is not None:
        customer.name = payload.name.strip()
    if payload.company is not None:
        customer.company = payload.company.strip() if payload.company else None
    if payload.phone is not None:
        customer.phone = payload.phone.strip() if payload.phone else None
    if payload.billing_address_line1 is not None:
        customer.billing_address_line1 = payload.billing_address_line1.strip() if payload.billing_address_line1 else None
    if payload.billing_address_line2 is not None:
        customer.billing_address_line2 = payload.billing_address_line2.strip() if payload.billing_address_line2 else None
    if payload.billing_city is not None:
        customer.billing_city = payload.billing_city.strip() if payload.billing_city else None
    if payload.billing_state is not None:
        customer.billing_state = payload.billing_state.strip() if payload.billing_state else None
    if payload.billing_postal_code is not None:
        customer.billing_postal_code = payload.billing_postal_code.strip() if payload.billing_postal_code else None
    if payload.billing_country is not None:
        customer.billing_country = payload.billing_country.strip() if payload.billing_country else None

    customer.version += 1
    db.commit()
    db.refresh(customer)

    return _to_customer_response(customer)
