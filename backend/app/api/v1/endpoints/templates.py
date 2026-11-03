from typing import List, Optional
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
from app.services.template_validation import validate_active_template
from app.models.catalog import Plan, Product, ProductVariant
from app.models.templates import QuotationTemplate, TemplateLine
from app.models.users import User
from app.schemas.common import PaginatedResponse
from app.schemas.templates import (
    QuotationTemplateCreate,
    QuotationTemplateResponse,
    QuotationTemplateUpdate,
    TemplateLineResponse,
)

router = APIRouter()


def _build_template_response(template: QuotationTemplate) -> QuotationTemplateResponse:
    lines_resp: List[TemplateLineResponse] = []
    for line in sorted(template.lines, key=lambda l: l.ordinal):
        lines_resp.append(
            TemplateLineResponse(
                id=line.id,
                template_id=line.template_id,
                ordinal=line.ordinal,
                product_id=line.product_id,
                variant_id=line.variant_id,
                quantity=line.quantity,
                line_kind=line.line_kind,
                product_name=line.product.name if line.product else None,
                variant_name=line.variant.name if line.variant else None,
            )
        )

    return QuotationTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        plan_id=template.plan_id,
        plan_name=template.plan.name if template.plan else None,
        validity_days=template.validity_days,
        active=template.active,
        version=template.version,
        created_at=template.created_at,
        updated_at=template.updated_at,
        lines=lines_resp,
    )


@router.get("", response_model=PaginatedResponse[QuotationTemplateResponse])
def list_quotation_templates(
    search: Optional[str] = Query(None),
    plan_id: Optional[uuid.UUID] = Query(None),
    active: Optional[bool] = Query(None),
    sort: str = Query("name", pattern="^(name|validity_days|created_at)$"), descending: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    query = select(QuotationTemplate)

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.where(func.lower(QuotationTemplate.name).like(search_term))

    if plan_id:
        query = query.where(QuotationTemplate.plan_id == plan_id)

    if active is not None:
        query = query.where(QuotationTemplate.active == active)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    items_query = (
        query.order_by(*ordering(sort, descending, {"name": QuotationTemplate.name, "validity_days": QuotationTemplate.validity_days, "created_at": QuotationTemplate.created_at}, QuotationTemplate.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    templates = db.scalars(items_query).all()

    return PaginatedResponse(
        items=[_build_template_response(t) for t in templates],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post(
    "",
    response_model=QuotationTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def create_quotation_template(response: Response,
    payload: QuotationTemplateCreate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    existing = db.scalar(
        select(QuotationTemplate).where(QuotationTemplate.name == payload.name)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Quotation template with name '{payload.name}' already exists.",
        )

    plan = db.scalar(select(Plan).where(Plan.id == payload.plan_id))
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Plan with id '{payload.plan_id}' not found.",
        )
    if not plan.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Referenced plan '{plan.name}' is archived/inactive.",
        )

    # Incomplete templates cannot be active
    if payload.active and not payload.lines:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="An active quotation template must contain at least one line.",
        )

    template = QuotationTemplate(
        name=payload.name,
        description=payload.description,
        plan_id=payload.plan_id,
        validity_days=payload.validity_days,
        active=payload.active,
    )
    db.add(template)
    db.flush()

    for line_data in payload.lines:
        prod = db.scalar(select(Product).where(Product.id == line_data.product_id))
        if not prod:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with id '{line_data.product_id}' not found.",
            )
        if not prod.active:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Referenced product '{prod.name}' is archived/inactive.",
            )
        if line_data.variant_id:
            variant = db.scalar(
                select(ProductVariant).where(
                    ProductVariant.id == line_data.variant_id,
                    ProductVariant.product_id == line_data.product_id,
                )
            )
            if not variant:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Variant with id '{line_data.variant_id}' not found for product '{prod.name}'.",
                )
            if not variant.active:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Referenced variant '{variant.name}' is archived/inactive.",
                )

        db.add(
            TemplateLine(
                template_id=template.id,
                ordinal=line_data.ordinal,
                product_id=line_data.product_id,
                variant_id=line_data.variant_id,
                quantity=line_data.quantity,
                line_kind=line_data.line_kind,
            )
        )

    try:
        db.commit()
        db.refresh(template)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    created_location(response, f"quotation-templates/{template.id}")
    return _build_template_response(template)


@router.get("/{template_id}", response_model=QuotationTemplateResponse)
def get_quotation_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    template = db.scalar(
        select(QuotationTemplate).where(QuotationTemplate.id == template_id)
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quotation template with id '{template_id}' not found.",
        )
    return _build_template_response(template)


@router.patch(
    "/{template_id}",
    response_model=QuotationTemplateResponse,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def update_quotation_template(
    template_id: uuid.UUID,
    payload: QuotationTemplateUpdate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    template = db.scalar(
        select(QuotationTemplate).where(QuotationTemplate.id == template_id)
    )
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quotation template with id '{template_id}' not found.",
        )

    if payload.name is not None and payload.name != template.name:
        existing = db.scalar(
            select(QuotationTemplate).where(
                QuotationTemplate.name == payload.name,
                QuotationTemplate.id != template_id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Quotation template with name '{payload.name}' already exists.",
            )
        template.name = payload.name

    if payload.description is not None:
        template.description = payload.description

    if payload.plan_id is not None:
        plan = db.scalar(select(Plan).where(Plan.id == payload.plan_id))
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Plan with id '{payload.plan_id}' not found.",
            )
        if not plan.active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Referenced plan '{plan.name}' is archived/inactive.",
            )
        template.plan_id = payload.plan_id

    if payload.validity_days is not None:
        template.validity_days = payload.validity_days

    if payload.lines is not None:
        for line in list(template.lines):
            db.delete(line)
        db.flush()
        for line_data in payload.lines:
            prod = db.scalar(select(Product).where(Product.id == line_data.product_id))
            if not prod:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with id '{line_data.product_id}' not found.",
                )
            if not prod.active:
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Referenced product '{prod.name}' is archived/inactive.",
                )
            if line_data.variant_id:
                variant = db.scalar(
                    select(ProductVariant).where(
                        ProductVariant.id == line_data.variant_id,
                        ProductVariant.product_id == line_data.product_id,
                    )
                )
                if not variant:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Variant with id '{line_data.variant_id}' not found for product '{prod.name}'.",
                    )
                if not variant.active:
                    db.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=f"Referenced variant '{variant.name}' is archived/inactive.",
                    )
            db.add(
                TemplateLine(
                    template_id=template.id,
                    ordinal=line_data.ordinal,
                    product_id=line_data.product_id,
                    variant_id=line_data.variant_id,
                    quantity=line_data.quantity,
                    line_kind=line_data.line_kind,
                )
            )

    # Validate final template state on every update
    final_active = payload.active if payload.active is not None else template.active
    final_lines_count = len(payload.lines) if payload.lines is not None else len(template.lines)
    if final_active and final_lines_count == 0:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="An active quotation template must contain at least one line.",
        )
    if final_active:
        final_lines = payload.lines if payload.lines is not None else list(template.lines)
        try:
            validate_active_template(db, template.plan_id, final_lines)
        except HTTPException:
            db.rollback()
            raise
    template.active = final_active

    template.version += 1
    try:
        db.commit()
        db.refresh(template)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    return _build_template_response(template)
