from app.schemas.validation import Money, MAX_INTEGER, required_text, not_null
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# --- Product Variants ---

class ProductVariantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    price_adjustment: Decimal = Field(default=Decimal("0.00"), description="Price adjustment relative to product base price")
    active: bool = True


class ProductVariantCreate(ProductVariantBase):
    _required_text = field_validator("name", mode="before")(required_text)
    price_adjustment: Money = Decimal("0.00")


class ProductVariantUpdate(BaseModel):
    _required_text = field_validator("name", mode="before")(required_text)
    _not_null = field_validator("price_adjustment", "active", mode="before")(not_null)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    price_adjustment: Optional[Money] = None
    active: Optional[bool] = None


class ProductVariantResponse(ProductVariantBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    effective_sales_price: Optional[Decimal] = None


# --- Products ---

class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: str = Field(..., min_length=1, max_length=64)
    sales_price: Decimal = Field(..., ge=0, description="Customer-facing base sales price")
    active: bool = True


class ProductCreate(ProductBase):
    _required_text = field_validator("name", "type", mode="before")(required_text)
    sales_price: Money = Field(ge=0)
    cost_price: Money = Field(..., ge=0, description="Internal cost price")
    notes: Optional[str] = None
    tax_rule_ids: List[uuid.UUID] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    _required_text = field_validator("name", "type", mode="before")(required_text)
    _not_null = field_validator("sales_price", "cost_price", "active", mode="before")(not_null)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = Field(None, min_length=1, max_length=64)
    sales_price: Optional[Money] = Field(None, ge=0)
    cost_price: Optional[Money] = Field(None, ge=0)
    notes: Optional[str] = None
    active: Optional[bool] = None
    tax_rule_ids: Optional[List[uuid.UUID]] = None


class ProductAdminResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cost_price: Decimal
    notes: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime
    variants: List[ProductVariantResponse] = Field(default_factory=list)
    tax_rule_ids: List[uuid.UUID] = Field(default_factory=list)


class ProductStaffResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime
    variants: List[ProductVariantResponse] = Field(default_factory=list)
    tax_rule_ids: List[uuid.UUID] = Field(default_factory=list)


# --- Plan Items (Included Products) ---

class PlanItemBase(BaseModel):
    ordinal: int = Field(..., ge=1, le=MAX_INTEGER)
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None
    included_quantity: int = Field(default=1, ge=1, le=MAX_INTEGER)


class PlanItemCreate(PlanItemBase):
    pass


class PlanItemResponse(PlanItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_id: uuid.UUID
    product_name: Optional[str] = None
    variant_name: Optional[str] = None


# --- Plans ---

class PlanBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    base_fee: Decimal = Field(..., ge=0, description="Base recurring fee for the plan")
    minimum_seats: int = Field(default=1, ge=1, le=MAX_INTEGER, description="Minimum seats included with base fee")
    extra_seat_unit_price: Decimal = Field(default=Decimal("0.00"), ge=0, description="Price per excess seat beyond minimum_seats")
    interval: str = Field(..., description="'DAILY', 'WEEKLY', 'MONTHLY', or 'YEARLY'")
    available_from: Optional[date] = None
    available_to: Optional[date] = None
    payment_term_days: int = Field(default=15, ge=0)
    allow_pause: bool = True
    allow_resume: bool = True
    allow_renewal: bool = True
    allow_early_closure: bool = True
    auto_close_on_expiry: bool = True
    active: bool = True

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
            raise ValueError("interval must be DAILY, WEEKLY, MONTHLY, or YEARLY")
        return upper


class PlanCreate(PlanBase):
    payment_term_days: int = Field(default=15, ge=0, le=365)
    _required_text = field_validator("name", mode="before")(required_text)
    base_fee: Money = Field(ge=0)
    extra_seat_unit_price: Money = Field(default=Decimal("0.00"), ge=0)
    items: List[PlanItemCreate] = Field(default_factory=list)
    tax_rule_ids: List[uuid.UUID] = Field(default_factory=list)


class PlanUpdate(BaseModel):
    _required_text = field_validator("name", mode="before")(required_text)
    _not_null = field_validator("base_fee", "extra_seat_unit_price", "minimum_seats", "payment_term_days", "interval", "active", "allow_pause", "allow_resume", "allow_renewal", "allow_early_closure", "auto_close_on_expiry", mode="before")(not_null)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    base_fee: Optional[Money] = Field(None, ge=0)
    minimum_seats: Optional[int] = Field(None, ge=1, le=MAX_INTEGER)
    extra_seat_unit_price: Optional[Money] = Field(None, ge=0)
    interval: Optional[str] = None
    available_from: Optional[date] = None
    available_to: Optional[date] = None
    payment_term_days: Optional[int] = Field(None, ge=0, le=365)
    allow_pause: Optional[bool] = None
    allow_resume: Optional[bool] = None
    allow_renewal: Optional[bool] = None
    allow_early_closure: Optional[bool] = None
    auto_close_on_expiry: Optional[bool] = None
    active: Optional[bool] = None
    items: Optional[List[PlanItemCreate]] = None
    tax_rule_ids: Optional[List[uuid.UUID]] = None

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            upper = v.upper()
            if upper not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
                raise ValueError("interval must be DAILY, WEEKLY, MONTHLY, or YEARLY")
            return upper
        return v


class PlanResponse(PlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime
    items: List[PlanItemResponse] = Field(default_factory=list)
    tax_rule_ids: List[uuid.UUID] = Field(default_factory=list)
