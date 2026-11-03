from app.schemas.validation import Money, Percentage, MAX_INTEGER, required_text
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import field_validator, BaseModel, ConfigDict, Field, model_validator


class DiscountRevisionBase(BaseModel):
    type: str = Field(..., description="'FIXED' or 'PERCENT'")
    amount: Optional[Decimal] = Field(None, gt=0, description="Fixed discount amount (if type is FIXED)")
    rate: Optional[Decimal] = Field(None, gt=0, le=100, description="Percentage discount rate 0-100 (if type is PERCENT)")
    minimum_purchase: Optional[Decimal] = Field(None, ge=0)
    minimum_quantity: Optional[int] = Field(None, ge=1, le=MAX_INTEGER)
    scope: str = Field(..., description="'PRODUCT' or 'SUBSCRIPTION'")
    valid_from: date
    valid_to: date
    product_ids: List[uuid.UUID] = Field(default_factory=list, description="Eligible products if scope is PRODUCT")

    @model_validator(mode="after")
    def validate_type_and_dates(self) -> "DiscountRevisionBase":
        type_upper = self.type.upper()
        if type_upper not in ("FIXED", "PERCENT"):
            raise ValueError("type must be FIXED or PERCENT")
        self.type = type_upper

        scope_upper = self.scope.upper()
        if scope_upper not in ("PRODUCT", "SUBSCRIPTION"):
            raise ValueError("scope must be PRODUCT or SUBSCRIPTION")
        self.scope = scope_upper

        if self.valid_to < self.valid_from:
            raise ValueError("valid_to cannot be earlier than valid_from")

        if self.type == "FIXED":
            if self.amount is None or self.amount <= 0:
                raise ValueError("amount must be positive for FIXED discount")
            if self.rate is not None:
                raise ValueError("rate must be null for FIXED discount")
        elif self.type == "PERCENT":
            if self.rate is None or self.rate <= 0 or self.rate > 100:
                raise ValueError("rate must be between 0 and 100 for PERCENT discount")
            if self.amount is not None:
                raise ValueError("amount must be null for PERCENT discount")

        if self.scope == "PRODUCT" and not self.product_ids:
            raise ValueError("At least one product must be specified for PRODUCT scope discount")

        return self


class DiscountRevisionCreate(DiscountRevisionBase):
    amount: Optional[Money] = Field(None, gt=0)
    minimum_purchase: Optional[Money] = Field(None, ge=0)
    rate: Optional[Percentage] = Field(None, gt=0)
    pass


class DiscountRevisionResponse(DiscountRevisionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    revision: int
    created_at: datetime


class DiscountRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    maximum_uses: Optional[int] = Field(None, ge=1, le=MAX_INTEGER, description="Global maximum redemption count")


class DiscountRuleCreate(DiscountRuleBase):
    _required_text = field_validator("name", mode="before")(required_text)
    initial_revision: DiscountRevisionCreate


class DiscountDeactivateRequest(BaseModel):
    disabled_from: Optional[date] = None
    reason: Optional[str] = None


class DiscountRuleResponse(DiscountRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    disabled_from: Optional[date] = None
    version: int
    created_at: datetime
    updated_at: datetime
    revisions: List[DiscountRevisionResponse] = Field(default_factory=list)
    current_revision: Optional[DiscountRevisionResponse] = None
    redemption_count: int = 0
