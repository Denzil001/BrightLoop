"""Validated subscription commands. Commercial values are calculated by the server."""
import uuid
from app.schemas.validation import MAX_INTEGER
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.pricing import PricingLineInput


class SubscriptionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: uuid.UUID
    plan_id: uuid.UUID
    template_id: uuid.UUID | None = None
    seat_quantity: int = Field(ge=1, le=MAX_INTEGER)
    start_date: date
    expiry_date: date
    payment_term_days: int | None = Field(default=None, ge=0, le=365)
    validity_days: int | None = Field(default=None, ge=0, le=365)
    lines: list[PricingLineInput] | None = None
    discount_id: uuid.UUID | None = None
    discount_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.expiry_date <= self.start_date:
            raise ValueError("Expiry date must be after the service start date.")
        return self


class DraftUpdate(SubscriptionDraft):
    expected_version: int = Field(ge=1)


class SubscriptionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    request_key: str = Field(min_length=8, max_length=128)
    action: Literal["ISSUE", "CONFIRM", "ACTIVATE", "ABANDON"]
    agreement_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=2000)


class LifecycleIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["PAUSE", "RESUME", "RENEW", "EARLY_CLOSE", "ADDON_CHANGE"]
    effective_date: date
    reason: str = Field(min_length=1, max_length=2000)
    # Complete, explicitly reviewed commercial proposal for renewal/add-on changes.
    proposal: SubscriptionDraft | None = None

    @model_validator(mode="after")
    def requires_proposal(self):
        if not self.reason.strip():
            raise ValueError("Give a reason for this change.")
        if (self.action in ("RENEW", "ADDON_CHANGE")) != (self.proposal is not None):
            raise ValueError("Supply commercial terms only for renewal or add-on changes.")
        return self


class LifecycleCommand(LifecycleIntent):
    expected_version: int = Field(ge=1)
    request_key: str = Field(min_length=8, max_length=128)


class ChangeRequestCreate(LifecycleIntent):
    expected_version: int = Field(ge=1)


class ChangeRequestReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["APPROVE", "REJECT"]
    reason: str = Field(min_length=1, max_length=2000)
    expected_version: int = Field(ge=1)
    request_key: str = Field(min_length=8, max_length=128)
