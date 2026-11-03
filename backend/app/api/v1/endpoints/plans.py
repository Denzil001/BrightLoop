from typing import List, Optional
import uuid
from decimal import Decimal
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
from app.core.datetime_utils import get_business_today
from app.models.catalog import Plan, PlanItem, Product, ProductVariant
from app.models.taxes import PlanTax, TaxRule
from app.models.users import User
from app.schemas.catalog import (
    PlanCreate,
    PlanItemCreate,
    PlanItemResponse,
    PlanResponse,
    PlanUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


def _build_plan_response(plan: Plan) -> PlanResponse:
    tax_ids = [t.tax_rule_id for t in plan.taxes]
    items_resp: List[PlanItemResponse] = []
    for item in sorted(plan.items, key=lambda i: i.ordinal):
        items_resp.append(
            PlanItemResponse(
                id=item.id,
                plan_id=item.plan_id,
                ordinal=item.ordinal,
                product_id=item.product_id,
                variant_id=item.variant_id,
                included_quantity=item.included_quantity,
                product_name=item.product.name if item.product else None,
                variant_name=item.variant.name if item.variant else None,
            )
        )

    return PlanResponse(
        id=plan.id,
        name=plan.name,
        description=plan.description,
        base_fee=plan.base_fee,
        minimum_seats=plan.minimum_seats,
        extra_seat_unit_price=plan.extra_seat_unit_price,
        interval=plan.interval,
        available_from=plan.available_from,
        available_to=plan.available_to,
        payment_term_days=plan.payment_term_days,
        allow_pause=plan.allow_pause,
        allow_resume=plan.allow_resume,
        allow_renewal=plan.allow_renewal,
        allow_early_closure=plan.allow_early_closure,
        auto_close_on_expiry=plan.auto_close_on_expiry,
        active=plan.active,
        version=plan.version,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        items=items_resp,
        tax_rule_ids=tax_ids,
    )


@router.get("", response_model=PaginatedResponse[PlanResponse])
def list_plans(
    search: Optional[str] = Query(None),
    interval: Optional[str] = Query(None, pattern="(?i)^(DAILY|WEEKLY|MONTHLY|YEARLY)$"),
    active: Optional[bool] = Query(None),
    availability: Optional[str] = Query(None, pattern="^(available|future|expired)$"),
    sort: str = Query("name", pattern="^(name|interval|base_fee|created_at)$"), descending: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    query = select(Plan)

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.where(func.lower(Plan.name).like(search_term))

    if interval:
        query = query.where(Plan.interval == interval.upper())

    if active is not None:
        query = query.where(Plan.active == active)
    today = get_business_today()
    if availability == "available":
        query = query.where((Plan.available_from.is_(None) | (Plan.available_from <= today)),
            (Plan.available_to.is_(None) | (Plan.available_to >= today)))
    elif availability == "future":
        query = query.where(Plan.available_from > today)
    elif availability == "expired":
        query = query.where(Plan.available_to < today)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    items_query = (
        query.order_by(*ordering(sort, descending, {"name": Plan.name, "interval": Plan.interval, "base_fee": Plan.base_fee, "created_at": Plan.created_at}, Plan.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    plans = db.scalars(items_query).all()

    return PaginatedResponse(
        items=[_build_plan_response(p) for p in plans],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def create_plan(response: Response,
    payload: PlanCreate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    existing = db.scalar(select(Plan).where(Plan.name == payload.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Plan with name '{payload.name}' already exists.",
        )

    if payload.available_from and payload.available_to and payload.available_to < payload.available_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="available_to cannot be earlier than available_from.",
        )

    plan = Plan(
        name=payload.name,
        description=payload.description,
        base_fee=payload.base_fee,
        minimum_seats=payload.minimum_seats,
        extra_seat_unit_price=payload.extra_seat_unit_price,
        interval=payload.interval,
        available_from=payload.available_from,
        available_to=payload.available_to,
        payment_term_days=payload.payment_term_days,
        allow_pause=payload.allow_pause,
        allow_resume=payload.allow_resume,
        allow_renewal=payload.allow_renewal,
        allow_early_closure=payload.allow_early_closure,
        auto_close_on_expiry=payload.auto_close_on_expiry,
        active=payload.active,
    )
    db.add(plan)
    db.flush()

    # Taxes
    for tr_id in payload.tax_rule_ids:
        tax_rule = db.scalar(select(TaxRule).where(TaxRule.id == tr_id))
        if not tax_rule:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tax rule with id '{tr_id}' not found.",
            )
        db.add(PlanTax(plan_id=plan.id, tax_rule_id=tr_id))

    # Items
    for item_data in payload.items:
        prod = db.scalar(select(Product).where(Product.id == item_data.product_id))
        if not prod:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with id '{item_data.product_id}' not found.",
            )
        if item_data.variant_id:
            variant = db.scalar(
                select(ProductVariant).where(
                    ProductVariant.id == item_data.variant_id,
                    ProductVariant.product_id == item_data.product_id,
                )
            )
            if not variant:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Variant with id '{item_data.variant_id}' not found for product '{prod.name}'.",
                )

        plan_item = PlanItem(
            plan_id=plan.id,
            ordinal=item_data.ordinal,
            product_id=item_data.product_id,
            variant_id=item_data.variant_id,
            included_quantity=item_data.included_quantity,
        )
        db.add(plan_item)

    try:
        db.commit()
        db.refresh(plan)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    created_location(response, f"plans/{plan.id}")
    return _build_plan_response(plan)


@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(
    plan_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    plan = db.scalar(select(Plan).where(Plan.id == plan_id))
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with id '{plan_id}' not found.",
        )
    return _build_plan_response(plan)


@router.patch(
    "/{plan_id}",
    response_model=PlanResponse,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    plan = db.scalar(select(Plan).where(Plan.id == plan_id))
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with id '{plan_id}' not found.",
        )

    if payload.name is not None and payload.name != plan.name:
        existing = db.scalar(
            select(Plan).where(Plan.name == payload.name, Plan.id != plan_id)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Plan with name '{payload.name}' already exists.",
            )
        plan.name = payload.name

    if payload.description is not None:
        plan.description = payload.description
    if payload.base_fee is not None:
        plan.base_fee = payload.base_fee
    if payload.minimum_seats is not None:
        plan.minimum_seats = payload.minimum_seats
    if payload.extra_seat_unit_price is not None:
        plan.extra_seat_unit_price = payload.extra_seat_unit_price
    if payload.interval is not None:
        plan.interval = payload.interval
    if payload.available_from is not None:
        plan.available_from = payload.available_from
    if payload.available_to is not None:
        plan.available_to = payload.available_to
    if payload.payment_term_days is not None:
        plan.payment_term_days = payload.payment_term_days
    if payload.allow_pause is not None:
        plan.allow_pause = payload.allow_pause
    if payload.allow_resume is not None:
        plan.allow_resume = payload.allow_resume
    if payload.allow_renewal is not None:
        plan.allow_renewal = payload.allow_renewal
    if payload.allow_early_closure is not None:
        plan.allow_early_closure = payload.allow_early_closure
    if payload.auto_close_on_expiry is not None:
        plan.auto_close_on_expiry = payload.auto_close_on_expiry
    if payload.active is not None:
        plan.active = payload.active

    if plan.available_from and plan.available_to and plan.available_to < plan.available_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="available_to cannot be earlier than available_from.",
        )

    if payload.tax_rule_ids is not None:
        for pt in list(plan.taxes):
            db.delete(pt)
        db.flush()
        for tr_id in payload.tax_rule_ids:
            tr = db.scalar(select(TaxRule).where(TaxRule.id == tr_id))
            if not tr:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tax rule with id '{tr_id}' not found.",
                )
            db.add(PlanTax(plan_id=plan.id, tax_rule_id=tr_id))

    if payload.items is not None:
        for item in list(plan.items):
            db.delete(item)
        db.flush()
        for item_data in payload.items:
            prod = db.scalar(select(Product).where(Product.id == item_data.product_id))
            if not prod:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with id '{item_data.product_id}' not found.",
                )
            if item_data.variant_id:
                variant = db.scalar(
                    select(ProductVariant).where(
                        ProductVariant.id == item_data.variant_id,
                        ProductVariant.product_id == item_data.product_id,
                    )
                )
                if not variant:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Variant with id '{item_data.variant_id}' not found for product '{prod.name}'.",
                    )
            db.add(
                PlanItem(
                    plan_id=plan.id,
                    ordinal=item_data.ordinal,
                    product_id=item_data.product_id,
                    variant_id=item_data.variant_id,
                    included_quantity=item_data.included_quantity,
                )
            )

    plan.version += 1
    try:
        db.commit()
        db.refresh(plan)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    return _build_plan_response(plan)


@router.post(
    "/{plan_id}/archive",
    response_model=PlanResponse,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def archive_plan(
    plan_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    plan = db.scalar(select(Plan).where(Plan.id == plan_id))
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with id '{plan_id}' not found.",
        )
    plan.active = False
    plan.version += 1
    db.commit()
    db.refresh(plan)
    return _build_plan_response(plan)
