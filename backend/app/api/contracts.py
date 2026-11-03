"""Shared transport rules; resource policies remain in their domain dependencies."""
from fastapi import Request, Response
from app.core.errors import ValidationException
from app.db.querying import ordering


def validate_query_parameters(request: Request):
    """Reject misspelled/ambiguous filters instead of silently ignoring them.

    Traverse FastAPI's resolved dependency declarations so parameters declared
    in reusable dependencies remain valid without a second hard-coded contract.
    """
    root = getattr(request.scope.get("route"), "dependant", None)
    allowed = set()
    def collect(dependant):
        if dependant is None:
            return
        allowed.update(field.alias for field in dependant.query_params)
        for child in dependant.dependencies:
            collect(child)
    collect(root)
    errors = []
    for name in request.query_params:
        if name not in allowed:
            errors.append({"path": f"query.{name}", "message": "Unknown query parameter. Check the supported filters."})
        elif len(request.query_params.getlist(name)) > 1:
            errors.append({"path": f"query.{name}", "message": "Supply this query parameter once."})
    if errors:
        raise ValidationException("Invalid query parameters.", fields=errors)


def created_location(response: Response, resource: str):
    response.headers["Location"] = f"/api/v1/{resource.lstrip('/')}"
