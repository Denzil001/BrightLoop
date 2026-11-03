from app.schemas.validation import MAX_INTEGER, Money
import uuid
from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class PricingLineInput(BaseModel):
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None
    quantity: int = Field(default=1, ge=1, le=MAX_INTEGER)
    agreed_unit_price: Optional[Money] = Field(None, ge=0)
    override_reason: Optional[str] = None
    line_kind: str = Field(default="ADDON", description="'INCLUDED' or 'ADDON'")

    @field_validator("line_kind")
    @classmethod
    def validate_line_kind(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ("INCLUDED", "ADDON"):
            raise ValueError("line_kind must be INCLUDED or ADDON")
        return upper


class PricingPreviewRequest(BaseModel):
    plan_id: uuid.UUID
    seat_quantity: int = Field(..., ge=1, le=MAX_INTEGER)
    lines: List[PricingLineInput] = Field(default_factory=list)
    discount_id: Optional[uuid.UUID] = None
    discount_revision_id: Optional[uuid.UUID] = None
    discount_ids: List[uuid.UUID] = Field(default_factory=list, max_length=10)
    discount_revision_ids: List[uuid.UUID] = Field(default_factory=list, max_length=10)
    as_of_date: Optional[date] = None


class PricingLineBreakdown(BaseModel):
    ordinal: int
    line_kind: str
    description: str
    product_id: Optional[uuid.UUID] = None
    variant_id: Optional[uuid.UUID] = None
    quantity: int
    unit_price: str
    subtotal: str
    discount_amount: str
    discounted_subtotal: str
    tax_amount: str
    total: str
    tax_rates: List[Decimal] = Field(default_factory=list)


class PricingTaxBreakdown(BaseModel):
    tax_rule_id: uuid.UUID
    name: str
    rate: Decimal
    taxable_base: str
    tax_amount: str


class PricingPreviewResponse(BaseModel):
    plan_name: str
    base_fee: str
    minimum_seats: int
    seat_quantity: int
    excess_seats: int
    extra_seat_unit_price: str
    excess_seat_amount: str
    subtotal: str
    total_discount: str
    taxable_amount: str
    total_tax: str
    total: str
    lines: List[PricingLineBreakdown]
    tax_breakdown: List[PricingTaxBreakdown]
    discount_applied: Optional[str] = None
    discount_revision_id: Optional[uuid.UUID] = None
    discount_ineligible_reason: Optional[str] = None
    assigned_discount_revision_ids: List[uuid.UUID] = Field(default_factory=list)
    applied_discount_revision_ids: List[uuid.UUID] = Field(default_factory=list)
