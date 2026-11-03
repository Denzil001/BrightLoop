from app.schemas.validation import required_text
import re
import uuid
from typing import Optional
from pydantic import BaseModel, Field, field_validator

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserDTO(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    role: str
    active: bool
    customer_id: Optional[uuid.UUID] = None


class RegisterRequest(BaseModel):
    _required_text = field_validator("name", mode="before")(required_text)
    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=9, max_length=1024)
    company: Optional[str] = Field(None, max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email address format.")
        return v


class RegisterResponse(BaseModel):
    message: str
    requires_verification: bool
    user: Optional[UserDTO] = None


class VerifySignupRequest(BaseModel):
    token: str = Field(..., min_length=10)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email address format.")
        return v


class LoginResponse(BaseModel):
    user: UserDTO
    csrf_token: str
    message: str = "Sign in successful"


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., max_length=255)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email address format.")
        return v


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=9, max_length=1024)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=1024)
    new_password: str = Field(..., min_length=9, max_length=1024)


class CsrfResponse(BaseModel):
    csrf_token: str
