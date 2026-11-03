from app.schemas.validation import Percentage, required_text, not_null
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import field_validator, BaseModel, ConfigDict, Field


class TaxRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    classification: str = Field(..., min_length=1, max_length=64)
    rate: Decimal = Field(..., ge=0, le=100, description="Tax rate percentage (0 to 100)")
    active: bool = True


class TaxRuleCreate(TaxRuleBase):
    _required_text = field_validator("name", "classification", mode="before")(required_text)
    rate: Percentage
    pass


class TaxRuleUpdate(BaseModel):
    _required_text = field_validator("name", "classification", mode="before")(required_text)
    _not_null = field_validator("rate", "active", mode="before")(not_null)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    classification: Optional[str] = Field(None, min_length=1, max_length=64)
    rate: Optional[Percentage] = Field(None, ge=0, le=100)
    active: Optional[bool] = None


class TaxRuleResponse(TaxRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime
