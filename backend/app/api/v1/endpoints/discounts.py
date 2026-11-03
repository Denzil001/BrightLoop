from datetime import date
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased
from app.api.contracts import created_location, ordering
from app.api.deps import (
    get_current_db,
    require_role,
    verify_csrf,
    verify_origin,
)
from app.core.datetime_utils import get_business_today
from app.core.errors import translate_database_error
from app.models.catalog import Product
from app.models.discounts import (
    DiscountProduct,
    DiscountRedemption,
    DiscountRevision,
    DiscountRule,
)
from app.models.users import User
from app.schemas.common import PaginatedResponse
from app.schemas.discounts import (
    DiscountDeactivateRequest,
    DiscountRevisionCreate,
    DiscountRevisionResponse,
    DiscountRuleCreate,
    DiscountRuleResponse,
)

router = APIRouter()


def _build_revision_response(revision: DiscountRevision) -> DiscountRevisionResponse:
    product_ids = [p.product_id for p in revision.products]
    return DiscountRevisionResponse(
        id=revision.id,
        rule_id=revision.rule_id,
        revision=revision.revision,
        type=revision.type,
        amount=revision.amount,
        rate=revision.rate,
        minimum_purchase=revision.minimum_purchase,
        minimum_quantity=revision.minimum_quantity,
        scope=revision.scope,
        valid_from=revision.valid_from,
        valid_to=revision.valid_to,
        created_at=revision.created_at,
        product_ids=product_ids,
    )


def _build_rule_response(rule: DiscountRule, db: Session) -> DiscountRuleResponse:
    revisions = sorted(rule.revisions, key=lambda r: r.revision, reverse=True)
    rev_responses = [_build_revision_response(r) for r in revisions]

    today = get_business_today()
    current_rev = next(
        (r for r in revisions if r.valid_from <= today <= r.valid_to),
        revisions[0] if revisions else None,
    )

    redemption_count = (
        db.scalar(
            select(func.count(DiscountRedemption.id)).where(
                DiscountRedemption.rule_id == rule.id
            )
        )
        or 0
    )

    return DiscountRuleResponse(
        id=rule.id,
        name=rule.name,
        maximum_uses=rule.maximum_uses,
        disabled_from=rule.disabled_from,
        version=rule.version,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        revisions=rev_responses,
        current_revision=_build_revision_response(current_rev) if current_rev else None,
        redemption_count=redemption_count,
    )


@router.get("", response_model=PaginatedResponse[DiscountRuleResponse])
def list_discounts(
    search: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
    scope: Optional[str] = Query(None, pattern="^(PRODUCT|SUBSCRIPTION)$"),
    discount_type: Optional[str] = Query(None, pattern="^(FIXED|PERCENT)$"),
    eligibility: Optional[str] = Query(None, pattern="^(eligible|not_yet_valid|expired|exhausted|disabled)$"),
    sort: str = Query("name", pattern="^(name|created_at)$"), descending: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    query = select(DiscountRule)
    today = get_business_today()
    if scope or discount_type or eligibility:
        current_id = select(DiscountRevision.id).where(DiscountRevision.rule_id == DiscountRule.id,
            DiscountRevision.valid_from <= today, DiscountRevision.valid_to >= today).order_by(
            DiscountRevision.revision.desc()).limit(1).correlate(DiscountRule).scalar_subquery()
        latest_id = select(DiscountRevision.id).where(DiscountRevision.rule_id == DiscountRule.id).order_by(
            DiscountRevision.revision.desc()).limit(1).correlate(DiscountRule).scalar_subquery()
        revision = aliased(DiscountRevision)
        query = query.outerjoin(revision, revision.id == func.coalesce(current_id, latest_id))
        if scope:
            query = query.where(revision.scope == scope)
        if discount_type:
            query = query.where(revision.type == discount_type)
        if eligibility:
            enabled = DiscountRule.disabled_from.is_(None) | (DiscountRule.disabled_from > today)
            in_window = and_(revision.valid_from <= today, revision.valid_to >= today)
            uses = select(func.count()).select_from(DiscountRedemption).where(
                DiscountRedemption.rule_id == DiscountRule.id).correlate(DiscountRule).scalar_subquery()
            exhausted = and_(DiscountRule.maximum_uses.is_not(None), uses >= DiscountRule.maximum_uses)
            states = {"disabled": ~enabled, "not_yet_valid": and_(enabled, revision.valid_from > today),
                "expired": and_(enabled, revision.valid_to < today), "exhausted": and_(enabled, in_window, exhausted),
                "eligible": and_(enabled, in_window, ~exhausted)}
            query = query.where(states[eligibility])

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.where(func.lower(DiscountRule.name).like(search_term))

    if active is not None:
        today = get_business_today()
        if active:
            query = query.where(
                (DiscountRule.disabled_from.is_(None)) | (DiscountRule.disabled_from > today)
            )
        else:
            query = query.where(
                DiscountRule.disabled_from.is_not(None),
                DiscountRule.disabled_from <= today,
            )

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    items_query = (
        query.order_by(*ordering(sort, descending, {"name": DiscountRule.name, "created_at": DiscountRule.created_at}, DiscountRule.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rules = db.scalars(items_query).all()

    return PaginatedResponse(
        items=[_build_rule_response(r, db) for r in rules],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=DiscountRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def create_discount_rule(response: Response,
    payload: DiscountRuleCreate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    existing = db.scalar(select(DiscountRule).where(DiscountRule.name == payload.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Discount rule with name '{payload.name}' already exists.",
        )

    rule = DiscountRule(
        name=payload.name,
        maximum_uses=payload.maximum_uses,
    )
    db.add(rule)
    db.flush()

    rev_data = payload.initial_revision
    revision = DiscountRevision(
        rule_id=rule.id,
        revision=1,
        type=rev_data.type,
        amount=rev_data.amount,
        rate=rev_data.rate,
        minimum_purchase=rev_data.minimum_purchase,
        minimum_quantity=rev_data.minimum_quantity,
        scope=rev_data.scope,
        valid_from=rev_data.valid_from,
        valid_to=rev_data.valid_to,
    )
    db.add(revision)
    db.flush()

    if rev_data.scope == "PRODUCT":
        for pid in rev_data.product_ids:
            prod = db.scalar(select(Product).where(Product.id == pid))
            if not prod:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with id '{pid}' not found.",
                )
            db.add(DiscountProduct(revision_id=revision.id, product_id=pid))

    try:
        db.commit()
        db.refresh(rule)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    created_location(response, f"discounts/{rule.id}")
    return _build_rule_response(rule, db)


@router.get("/{discount_id}", response_model=DiscountRuleResponse)
def get_discount_rule(
    discount_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    rule = db.scalar(select(DiscountRule).where(DiscountRule.id == discount_id))
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discount rule with id '{discount_id}' not found.",
        )
    return _build_rule_response(rule, db)


@router.post(
    "/{discount_id}/revisions",
    response_model=DiscountRuleResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def create_discount_revision(response: Response,
    discount_id: uuid.UUID,
    payload: DiscountRevisionCreate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    rule = db.scalar(select(DiscountRule).where(DiscountRule.id == discount_id))
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discount rule with id '{discount_id}' not found.",
        )

    max_rev = db.scalar(
        select(func.max(DiscountRevision.revision)).where(
            DiscountRevision.rule_id == discount_id
        )
    ) or 0
    new_rev_number = max_rev + 1

    revision = DiscountRevision(
        rule_id=rule.id,
        revision=new_rev_number,
        type=payload.type,
        amount=payload.amount,
        rate=payload.rate,
        minimum_purchase=payload.minimum_purchase,
        minimum_quantity=payload.minimum_quantity,
        scope=payload.scope,
        valid_from=payload.valid_from,
        valid_to=payload.valid_to,
    )
    db.add(revision)
    db.flush()

    if payload.scope == "PRODUCT":
        for pid in payload.product_ids:
            prod = db.scalar(select(Product).where(Product.id == pid))
            if not prod:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with id '{pid}' not found.",
                )
            db.add(DiscountProduct(revision_id=revision.id, product_id=pid))

    rule.version += 1

    try:
        db.commit()
        db.refresh(rule)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    created_location(response, f"discounts/{rule.id}")
    return _build_rule_response(rule, db)


@router.post(
    "/{discount_id}/deactivate",
    response_model=DiscountRuleResponse,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def deactivate_discount_rule(
    discount_id: uuid.UUID,
    payload: DiscountDeactivateRequest,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    rule = db.scalar(select(DiscountRule).where(DiscountRule.id == discount_id))
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discount rule with id '{discount_id}' not found.",
        )

    business_today = get_business_today()
    disabled_date = payload.disabled_from or business_today

    if disabled_date < business_today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Discount deactivation cannot be backdated before current business date ({business_today}).",
        )

    if rule.disabled_from is not None:
        if rule.disabled_from <= business_today and disabled_date != rule.disabled_from:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot modify an already effective historical cutoff date ({rule.disabled_from}).",
            )

    rule.disabled_from = disabled_date
    rule.version += 1
    db.commit()
    db.refresh(rule)
    return _build_rule_response(rule, db)


@router.get("/{discount_id}/redemptions")
def get_discount_redemptions(
    discount_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    rule = db.scalar(select(DiscountRule).where(DiscountRule.id == discount_id))
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Discount rule with id '{discount_id}' not found.",
        )

    # In Phase 3, no redemptions exist yet
    return {
        "items": [],
        "page": page,
        "page_size": page_size,
        "total": 0,
    }
