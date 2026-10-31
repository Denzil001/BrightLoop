from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.deps import (
    get_current_db,
    get_current_user,
    verify_csrf,
)
from app.models.customers import Customer
from app.models.users import User
from app.schemas.customers import CustomerProfileUpdate

router = APIRouter()


@router.get("", response_model=Dict[str, Any])
def get_own_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_current_db),
):
    if user.role == "CUSTOMER":
        customer = db.scalar(select(Customer).where(Customer.user_id == user.id))
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer record not found.")
        return {
            "id": str(user.id),
            "customer_id": str(customer.id),
            "name": customer.name,
            "email": user.email_normalized,
            "role": user.role,
            "company": customer.company,
            "phone": customer.phone,
            "billing_address_line1": customer.billing_address_line1,
            "billing_address_line2": customer.billing_address_line2,
            "billing_city": customer.billing_city,
            "billing_state": customer.billing_state,
            "billing_postal_code": customer.billing_postal_code,
            "billing_country": customer.billing_country,
            "version": customer.version,
            "created_at": customer.created_at.isoformat(),
            "updated_at": customer.updated_at.isoformat(),
        }

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email_normalized,
        "role": user.role,
        "version": user.version,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }


@router.patch("", response_model=Dict[str, Any])
def update_own_profile(
    payload: CustomerProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_current_db),
    _: None = Depends(verify_csrf),
):
    if user.role == "CUSTOMER":
        customer = db.scalar(select(Customer).where(Customer.user_id == user.id))
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer record not found.")

        if payload.name is not None:
            customer.name = payload.name.strip()
            user.name = payload.name.strip()
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
        user.version += 1
        db.commit()
        db.refresh(customer)
        db.refresh(user)

        return {
            "id": str(user.id),
            "customer_id": str(customer.id),
            "name": customer.name,
            "email": user.email_normalized,
            "role": user.role,
            "company": customer.company,
            "phone": customer.phone,
            "billing_address_line1": customer.billing_address_line1,
            "billing_address_line2": customer.billing_address_line2,
            "billing_city": customer.billing_city,
            "billing_state": customer.billing_state,
            "billing_postal_code": customer.billing_postal_code,
            "billing_country": customer.billing_country,
            "version": customer.version,
            "created_at": customer.created_at.isoformat(),
            "updated_at": customer.updated_at.isoformat(),
        }

    # For ADMIN or STAFF, only update name
    if payload.name is not None:
        user.name = payload.name.strip()
        user.version += 1
        db.commit()
        db.refresh(user)

    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email_normalized,
        "role": user.role,
        "version": user.version,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
    }
