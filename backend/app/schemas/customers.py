from app.schemas.validation import required_text
import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CustomerCreate(BaseModel):
    _required_text = field_validator("name", mode="before")(required_text)
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=64)
    billing_address_line1: Optional[str] = Field(None, max_length=255)
    billing_address_line2: Optional[str] = Field(None, max_length=255)
    billing_city: Optional[str] = Field(None, max_length=128)
    billing_state: Optional[str] = Field(None, max_length=128)
    billing_postal_code: Optional[str] = Field(None, max_length=32)
    billing_country: Optional[str] = Field(None, max_length=64)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email address format.")
        return v


class CustomerUpdate(BaseModel):
    _required_text = field_validator("name", mode="before")(required_text)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=64)
    billing_address_line1: Optional[str] = Field(None, max_length=255)
    billing_address_line2: Optional[str] = Field(None, max_length=255)
    billing_city: Optional[str] = Field(None, max_length=128)
    billing_state: Optional[str] = Field(None, max_length=128)
    billing_postal_code: Optional[str] = Field(None, max_length=32)
    billing_country: Optional[str] = Field(None, max_length=64)
    expected_version: Optional[int] = None


class CustomerProfileUpdate(BaseModel):
    _required_text = field_validator("name", mode="before")(required_text)
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=64)
    billing_address_line1: Optional[str] = Field(None, max_length=255)
    billing_address_line2: Optional[str] = Field(None, max_length=255)
    billing_city: Optional[str] = Field(None, max_length=128)
    billing_state: Optional[str] = Field(None, max_length=128)
    billing_postal_code: Optional[str] = Field(None, max_length=32)
    billing_country: Optional[str] = Field(None, max_length=64)


class OwnProfileUpdate(BaseModel):
    _required_text = field_validator("name", mode="before")(required_text)
    name: Optional[str] = Field(None, min_length=1, max_length=255)


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    company: Optional[str] = None
    phone: Optional[str] = None
    billing_address_line1: Optional[str] = None
    billing_address_line2: Optional[str] = None
    billing_city: Optional[str] = None
    billing_state: Optional[str] = None
    billing_postal_code: Optional[str] = None
    billing_country: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    has_portal_login: bool
    version: int
    created_at: datetime
    updated_at: datetime


class CustomerListResponse(BaseModel):
    items: list[CustomerResponse]
    page: int
    page_size: int
    total: int
