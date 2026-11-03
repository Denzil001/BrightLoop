"""Shared SQL collection ordering with fixed, caller-owned field maps."""
from app.core.errors import ValidationException


def ordering(name, descending, columns, identity):
    if name not in columns:
        raise ValidationException("Unsupported sort field.", fields=[{"path": "query.sort", "message": "Choose an available sort field for this view."}])
    column = columns[name]
    return [(column.desc() if descending else column.asc()).nulls_last(), identity.asc()]
