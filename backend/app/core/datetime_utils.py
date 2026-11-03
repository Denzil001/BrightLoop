from datetime import date, datetime
from zoneinfo import ZoneInfo
from app.core.config import get_settings


def get_business_today() -> date:
    """Return the current calendar date in the configured business timezone (Asia/Kolkata)."""
    tz = ZoneInfo(get_settings().TIMEZONE)
    return datetime.now(tz).date()


def get_business_now() -> datetime:
    """Return the current timezone-aware datetime in the configured business timezone."""
    tz = ZoneInfo(get_settings().TIMEZONE)
    return datetime.now(tz)
