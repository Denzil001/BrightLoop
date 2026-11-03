from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.contracts import created_location, ordering
from app.api.deps import (
    get_current_db,
    require_role,
    verify_csrf,
    verify_origin,
)
from app.core.errors import translate_database_error
from app.models.taxes import TaxRule
from app.models.users import User
from app.schemas.common import PaginatedResponse
from app.schemas.taxes import TaxRuleCreate, TaxRuleResponse, TaxRuleUpdate

router = APIRouter()


@router.get("", response_model=PaginatedResponse[TaxRuleResponse])
def list_tax_rules(
    search: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
    sort: str = Query("created_at", pattern="^(name|rate|created_at)$"), descending: bool = True,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    query = select(TaxRule)

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.where(
            (func.lower(TaxRule.name).like(search_term))
            | (func.lower(TaxRule.classification).like(search_term))
        )

    if active is not None:
        query = query.where(TaxRule.active == active)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    items_query = (
        query.order_by(*ordering(sort, descending, {"name": TaxRule.name, "rate": TaxRule.rate, "created_at": TaxRule.created_at}, TaxRule.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rules = db.scalars(items_query).all()

    return PaginatedResponse(
        items=[TaxRuleResponse.model_validate(r) for r in rules],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=TaxRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def create_tax_rule(response: Response,
    payload: TaxRuleCreate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    existing = db.scalar(select(TaxRule).where(TaxRule.name == payload.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tax rule with name '{payload.name}' already exists.",
        )

    rule = TaxRule(
        name=payload.name,
        classification=payload.classification,
        rate=payload.rate,
        active=payload.active,
    )
    db.add(rule)
    try:
        db.commit()
        db.refresh(rule)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    created_location(response, f"taxes/{rule.id}")
    return TaxRuleResponse.model_validate(rule)


@router.get("/{tax_id}", response_model=TaxRuleResponse)
def get_tax_rule(
    tax_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    rule = db.scalar(select(TaxRule).where(TaxRule.id == tax_id))
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax rule with id '{tax_id}' not found.",
        )
    return TaxRuleResponse.model_validate(rule)


@router.patch(
    "/{tax_id}",
    response_model=TaxRuleResponse,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def update_tax_rule(
    tax_id: uuid.UUID,
    payload: TaxRuleUpdate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    rule = db.scalar(select(TaxRule).where(TaxRule.id == tax_id))
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tax rule with id '{tax_id}' not found.",
        )

    if payload.name is not None and payload.name != rule.name:
        existing = db.scalar(
            select(TaxRule).where(TaxRule.name == payload.name, TaxRule.id != tax_id)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tax rule with name '{payload.name}' already exists.",
            )
        rule.name = payload.name

    if payload.classification is not None:
        rule.classification = payload.classification

    if payload.rate is not None:
        rule.rate = payload.rate

    if payload.active is not None:
        rule.active = payload.active

    rule.version += 1

    try:
        db.commit()
        db.refresh(rule)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    return TaxRuleResponse.model_validate(rule)
