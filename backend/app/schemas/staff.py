import re
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class StaffCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., max_length=255)
    initial_password: str = Field(..., min_length=9)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email address format.")
        return v


class StaffUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    expected_version: Optional[int] = None


class StaffResponse(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    active: bool
    version: int
    created_at: datetime
    updated_at: datetime


class StaffListResponse(BaseModel):
    items: list[StaffResponse]
    page: int
    page_size: int
    total: int
