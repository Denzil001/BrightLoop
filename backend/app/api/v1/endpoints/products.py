from typing import List, Optional, Union
import uuid
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.limits import MAX_MONEY
from app.api.contracts import created_location, ordering
from app.api.deps import (
    get_current_db,
    get_current_user,
    require_role,
    verify_csrf,
    verify_origin,
)
from app.core.errors import translate_database_error
from app.models.catalog import Product, ProductVariant
from app.models.taxes import ProductTax, TaxRule
from app.models.users import User
from app.schemas.catalog import (
    ProductAdminResponse,
    ProductCreate,
    ProductStaffResponse,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantResponse,
    ProductVariantUpdate,
)
from app.schemas.common import PaginatedResponse

router = APIRouter()


@router.get("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
def get_product_variant(product_id: uuid.UUID, variant_id: uuid.UUID, db: Session = Depends(get_current_db),
                        _: User = Depends(require_role(["ADMIN", "STAFF"]))):
    variant = db.scalar(select(ProductVariant).where(ProductVariant.id == variant_id,
        ProductVariant.product_id == product_id))
    if variant is None:
        raise HTTPException(404, "Product variant not found.")
    return _build_variant_response(variant, variant.product.sales_price)


def _validate_effective_price(base: Decimal, adjustment: Decimal, name: str):
    effective = base + adjustment
    if effective < 0:
        raise HTTPException(status_code=422, detail=f"Variant '{name}' effective sales price cannot be negative.")
    if effective > MAX_MONEY:
        raise HTTPException(status_code=422, detail=f"Variant '{name}' effective sales price exceeds the supported monetary range.")
    return effective


def _build_variant_response(variant: ProductVariant, base_price: Decimal) -> ProductVariantResponse:
    effective = base_price + variant.price_adjustment
    resp = ProductVariantResponse.model_validate(variant)
    resp.effective_sales_price = effective
    return resp


def _build_product_response(
    product: Product, is_admin: bool
) -> Union[ProductAdminResponse, ProductStaffResponse]:
    tax_ids = [t.tax_rule_id for t in product.taxes]
    variants = [_build_variant_response(v, product.sales_price) for v in product.variants]

    if is_admin:
        return ProductAdminResponse(
            id=product.id,
            name=product.name,
            type=product.type,
            sales_price=product.sales_price,
            cost_price=product.cost_price,
            notes=product.notes,
            active=product.active,
            version=product.version,
            created_at=product.created_at,
            updated_at=product.updated_at,
            variants=variants,
            tax_rule_ids=tax_ids,
        )
    else:
        return ProductStaffResponse(
            id=product.id,
            name=product.name,
            type=product.type,
            sales_price=product.sales_price,
            active=product.active,
            version=product.version,
            created_at=product.created_at,
            updated_at=product.updated_at,
            variants=variants,
            tax_rule_ids=tax_ids,
        )


@router.get("")
def list_products(
    search: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
    sort: str = Query("name", pattern="^(name|type|sales_price|created_at)$"), descending: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_current_db),
    current_user: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    query = select(Product)

    if search:
        search_term = f"%{search.strip().lower()}%"
        query = query.where(
            (func.lower(Product.name).like(search_term))
            | (func.lower(Product.type).like(search_term))
        )

    if active is not None:
        query = query.where(Product.active == active)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0

    items_query = (
        query.order_by(*ordering(sort, descending, {"name": Product.name, "type": Product.type, "sales_price": Product.sales_price, "created_at": Product.created_at}, Product.id))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    products = db.scalars(items_query).all()

    is_admin = current_user.role == "ADMIN"
    items = [_build_product_response(p, is_admin) for p in products]

    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post(
    "",
    response_model=ProductAdminResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def create_product(response: Response,
    payload: ProductCreate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    existing = db.scalar(select(Product).where(Product.name == payload.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with name '{payload.name}' already exists.",
        )

    product = Product(
        name=payload.name,
        type=payload.type,
        sales_price=payload.sales_price,
        cost_price=payload.cost_price,
        notes=payload.notes,
        active=payload.active,
    )
    db.add(product)
    db.flush()

    for tr_id in payload.tax_rule_ids:
        tax_rule = db.scalar(select(TaxRule).where(TaxRule.id == tr_id))
        if not tax_rule:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tax rule with id '{tr_id}' not found.",
            )
        db.add(ProductTax(product_id=product.id, tax_rule_id=tr_id))

    try:
        db.commit()
        db.refresh(product)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    created_location(response, f"products/{product.id}")
    return _build_product_response(product, is_admin=True)


@router.get("/{product_id}")
def get_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    current_user: User = Depends(require_role(["STAFF", "ADMIN"])),
):
    product = db.scalar(select(Product).where(Product.id == product_id))
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id '{product_id}' not found.",
        )
    is_admin = current_user.role == "ADMIN"
    return _build_product_response(product, is_admin)


@router.patch(
    "/{product_id}",
    response_model=ProductAdminResponse,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id '{product_id}' not found.",
        )

    if payload.name is not None and payload.name != product.name:
        existing = db.scalar(
            select(Product).where(Product.name == payload.name, Product.id != product_id)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product with name '{payload.name}' already exists.",
            )
        product.name = payload.name

    if payload.type is not None:
        product.type = payload.type
    if payload.sales_price is not None:
        # Parent row locking serializes base-price and variant changes.
        for variant in product.variants:
            _validate_effective_price(payload.sales_price, variant.price_adjustment, variant.name)
        product.sales_price = payload.sales_price
    if payload.cost_price is not None:
        product.cost_price = payload.cost_price
    if payload.notes is not None:
        product.notes = payload.notes
    if payload.active is not None:
        product.active = payload.active

    if payload.tax_rule_ids is not None:
        # Replace tax associations
        for pt in list(product.taxes):
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
            db.add(ProductTax(product_id=product.id, tax_rule_id=tr_id))

    product.version += 1
    try:
        db.commit()
        db.refresh(product)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    return _build_product_response(product, is_admin=True)


@router.post(
    "/{product_id}/archive",
    response_model=ProductAdminResponse,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def archive_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id '{product_id}' not found.",
        )
    product.active = False
    product.version += 1
    db.commit()
    db.refresh(product)
    return _build_product_response(product, is_admin=True)


# --- Variants Sub-resource ---

@router.post(
    "/{product_id}/variants",
    response_model=ProductVariantResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def create_product_variant(response: Response,
    product_id: uuid.UUID,
    payload: ProductVariantCreate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id '{product_id}' not found.",
        )

    _validate_effective_price(product.sales_price, payload.price_adjustment, payload.name)

    existing = db.scalar(
        select(ProductVariant).where(
            ProductVariant.product_id == product_id,
            ProductVariant.name == payload.name,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Variant with name '{payload.name}' already exists for this product.",
        )

    variant = ProductVariant(
        product_id=product_id,
        name=payload.name,
        price_adjustment=payload.price_adjustment,
        active=payload.active,
    )
    db.add(variant)
    try:
        db.commit()
        db.refresh(variant)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    created_location(response, f"products/{product_id}/variants/{variant.id}")
    return _build_variant_response(variant, product.sales_price)


@router.patch(
    "/{product_id}/variants/{variant_id}",
    response_model=ProductVariantResponse,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def update_product_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    payload: ProductVariantUpdate,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id '{product_id}' not found.",
        )

    variant = db.scalar(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with id '{variant_id}' not found on product '{product.name}'.",
        )

    if payload.name is not None and payload.name != variant.name:
        existing = db.scalar(
            select(ProductVariant).where(
                ProductVariant.product_id == product_id,
                ProductVariant.name == payload.name,
                ProductVariant.id != variant_id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Variant with name '{payload.name}' already exists for this product.",
            )
        variant.name = payload.name

    if payload.price_adjustment is not None:
        _validate_effective_price(product.sales_price, payload.price_adjustment, variant.name)
        variant.price_adjustment = payload.price_adjustment

    if payload.active is not None:
        variant.active = payload.active

    try:
        db.commit()
        db.refresh(variant)
    except IntegrityError as e:
        db.rollback()
        raise translate_database_error(e)

    return _build_variant_response(variant, product.sales_price)


@router.post(
    "/{product_id}/variants/{variant_id}/archive",
    response_model=ProductVariantResponse,
    dependencies=[Depends(verify_origin), Depends(verify_csrf)],
)
def archive_product_variant(
    product_id: uuid.UUID,
    variant_id: uuid.UUID,
    db: Session = Depends(get_current_db),
    _: User = Depends(require_role(["ADMIN"])),
):
    product = db.scalar(select(Product).where(Product.id == product_id).with_for_update())
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id '{product_id}' not found.",
        )

    variant = db.scalar(
        select(ProductVariant).where(
            ProductVariant.id == variant_id,
            ProductVariant.product_id == product_id,
        )
    )
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variant with id '{variant_id}' not found on product '{product.name}'.",
        )

    variant.active = False
    db.commit()
    db.refresh(variant)
    return _build_variant_response(variant, product.sales_price)
