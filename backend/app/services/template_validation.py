"""Validation of the complete resulting template, including retained references."""
from fastapi import HTTPException
from sqlalchemy import select
from app.models.catalog import Plan, Product, ProductVariant


def validate_active_template(db, plan_id, lines):
    plan = db.scalar(select(Plan).where(Plan.id == plan_id))
    if not plan or not plan.active:
        raise HTTPException(400, "An active template requires an active plan.")
    if not lines:
        raise HTTPException(400, "An active quotation template must contain at least one line.")
    for line in lines:
        product = db.scalar(select(Product).where(Product.id == line.product_id))
        if not product or not product.active:
            raise HTTPException(400, "An active template requires active product references.")
        if line.variant_id:
            variant = db.scalar(select(ProductVariant).where(
                ProductVariant.id == line.variant_id,
                ProductVariant.product_id == line.product_id,
            ))
            if not variant or not variant.active:
                raise HTTPException(400, "An active template requires active variants belonging to its products.")
