from app.schemas.validation import MAX_INTEGER, required_text, not_null
import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TemplateLineBase(BaseModel):
    ordinal: int = Field(..., ge=1, le=MAX_INTEGER)
    product_id: uuid.UUID
    variant_id: Optional[uuid.UUID] = None
    quantity: int = Field(default=1, ge=1)
    line_kind: str = Field(..., description="'INCLUDED' or 'ADDON'")

    @field_validator("line_kind")
    @classmethod
    def validate_line_kind(cls, v: str) -> str:
        upper = v.upper()
        if upper not in ("INCLUDED", "ADDON"):
            raise ValueError("line_kind must be INCLUDED or ADDON")
        return upper


class TemplateLineCreate(TemplateLineBase):
    pass


class TemplateLineResponse(TemplateLineBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    template_id: uuid.UUID
    product_name: Optional[str] = None
    variant_name: Optional[str] = None


class QuotationTemplateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    plan_id: uuid.UUID
    validity_days: int = Field(default=30, gt=0)
    active: bool = True


class QuotationTemplateCreate(QuotationTemplateBase):
    validity_days: int = Field(default=30, gt=0, le=365)
    _required_text = field_validator("name", mode="before")(required_text)
    lines: List[TemplateLineCreate] = Field(default_factory=list)


class QuotationTemplateUpdate(BaseModel):
    _required_text = field_validator("name", mode="before")(required_text)
    _not_null = field_validator("plan_id", "validity_days", "active", mode="before")(not_null)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    plan_id: Optional[uuid.UUID] = None
    validity_days: Optional[int] = Field(None, gt=0, le=365)
    active: Optional[bool] = None
    lines: Optional[List[TemplateLineCreate]] = None


class QuotationTemplateResponse(QuotationTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan_name: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime
    lines: List[TemplateLineResponse] = Field(default_factory=list)
