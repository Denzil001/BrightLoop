from app.schemas.validation import required_text
from datetime import date
import re
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BillingRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    as_of_date: date
    after_subscription_id: uuid.UUID | None = None
    max_periods: int = Field(default=100, ge=1, le=100)
    subscription_id: uuid.UUID | None = None
    retry_of_id: uuid.UUID | None = None


class InvoiceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["CONFIRM", "CANCEL"]
    expected_version: int = Field(ge=1)
    request_key: str = Field(min_length=8, max_length=128)
    reason: str | None = Field(default=None, max_length=2000)


class BillingAddress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=255)
    state: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str | None = Field(default=None, max_length=128)


class InvoiceMetadataUpdate(BaseModel):
    _required_text = field_validator("customer_name", "reason", mode="before")(required_text)
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=2000)
    due_date: date | None = None
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    customer_email: str | None = Field(default=None, max_length=255)
    customer_company: str | None = Field(default=None, max_length=255)
    customer_address: BillingAddress | None = None

    @field_validator("customer_email")
    @classmethod
    def valid_email(cls, value):
        if value is not None and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("Enter a valid billing email address.")
        return value.strip().lower() if value else value
