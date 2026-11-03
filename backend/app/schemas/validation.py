"""Input constraints matching PostgreSQL storage; credentials are never trimmed."""
from decimal import Decimal
from typing import Annotated

from pydantic import BeforeValidator, Field
from app.core.limits import MAX_INTEGER as MAX_INTEGER

def money_input(value):
    if not isinstance(value, (str, Decimal)):
        raise ValueError("Send monetary amounts as decimal strings to preserve precision.")
    return value


Money = Annotated[Decimal, BeforeValidator(money_input, json_schema_input_type=str), Field(max_digits=18, decimal_places=2, allow_inf_nan=False)]
Percentage = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4, allow_inf_nan=False)]


def required_text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Enter a value containing at least one non-whitespace character.")
    return value.strip()


def not_null(value):
    if value is None:
        raise ValueError("This field cannot be null.")
    return value
