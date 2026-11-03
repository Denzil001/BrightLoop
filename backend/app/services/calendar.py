"""Business calendar boundaries preserve the original month/day anchor."""
from calendar import monthrange
from datetime import date, timedelta


def boundary(anchor: date, interval: str, offset: int) -> date:
    if offset < 0:
        raise ValueError("Boundary offset cannot be negative.")
    if interval == "DAILY":
        return anchor + timedelta(days=offset)
    if interval == "WEEKLY":
        return anchor + timedelta(days=7 * offset)
    if interval == "MONTHLY":
        month_index = anchor.year * 12 + anchor.month - 1 + offset
        year, month = divmod(month_index, 12)
        month += 1
        return date(year, month, min(anchor.day, monthrange(year, month)[1]))
    if interval == "YEARLY":
        year = anchor.year + offset
        return date(year, anchor.month, min(anchor.day, monthrange(year, anchor.month)[1]))
    raise ValueError("Unsupported billing interval.")


def is_boundary(anchor: date, interval: str, target: date) -> bool:
    if target < anchor:
        return False
    if interval == "DAILY":
        return True
    if interval == "WEEKLY":
        return (target - anchor).days % 7 == 0
    offset = (target.year - anchor.year) * 12 + target.month - anchor.month if interval == "MONTHLY" else target.year - anchor.year
    return boundary(anchor, interval, offset) == target
