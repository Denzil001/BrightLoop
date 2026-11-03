from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.datetime_utils import get_business_today
from app.schemas.validation import Money


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Money = Field(gt=0)
    method: Literal["CASH", "BANK_TRANSFER", "UPI", "CARD", "CHEQUE", "OTHER"]
    payment_date: date
    note: str = Field(min_length=1, max_length=2000)
    reference: str | None = Field(default=None, max_length=128)
    request_key: str = Field(min_length=8, max_length=128)

    @field_validator("note")
    @classmethod
    def meaningful_note(cls, value):
        if not value.strip():
            raise ValueError("Give a customer-visible payment note.")
        return value.strip()

    @field_validator("reference")
    @classmethod
    def clean_reference(cls, value):
        return value.strip() or None if value is not None else None

    @field_validator("request_key")
    @classmethod
    def meaningful_request_key(cls, value):
        value = value.strip()
        if len(value) < 8:
            raise ValueError("Use a non-empty payment request key of at least eight characters.")
        return value

    @model_validator(mode="after")
    def payment_not_future(self):
        if self.payment_date > get_business_today():
            raise ValueError("The payment date cannot be in the future.")
        return self
