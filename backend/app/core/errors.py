import uuid
from typing import Any, List, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorField(BaseModel):
    path: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    fields: Optional[List[ErrorField]] = None
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        fields: Optional[List[dict]] = None,
        headers: Optional[dict] = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.fields = [ErrorField(**f) for f in fields] if fields else None
        self.headers = headers
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND"):
        super().__init__(status.HTTP_404_NOT_FOUND, code, message)


class ForbiddenException(AppException):
    def __init__(self, message: str = "Permission denied", code: str = "FORBIDDEN"):
        super().__init__(status.HTTP_403_FORBIDDEN, code, message)


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Authentication required", code: str = "UNAUTHORIZED"):
        super().__init__(status.HTTP_401_UNAUTHORIZED, code, message)


class ConflictException(AppException):
    def __init__(self, message: str, code: str = "CONFLICT"):
        super().__init__(status.HTTP_409_CONFLICT, code, message)


class ValidationException(AppException):
    def __init__(self, message: str, fields: Optional[List[dict]] = None, code: str = "VALIDATION_ERROR"):
        super().__init__(status.HTTP_422_UNPROCESSABLE_CONTENT, code, message, fields)


class ServiceUnavailableException(AppException):
    def __init__(self, message: str = "Service unavailable", code: str = "SERVICE_UNAVAILABLE"):
        super().__init__(status.HTTP_503_SERVICE_UNAVAILABLE, code, message)


def translate_database_error(e: IntegrityError) -> AppException:
    """Translates database integrity errors into safe structured AppException without disclosing SQL, parameters, or database internals."""
    err_str = str(e).lower()
    if "unique constraint" in err_str or "duplicate key" in err_str or "uq_" in err_str:
        return ConflictException(message="A resource with these unique properties already exists.")
    if "foreign key constraint" in err_str or "fk_" in err_str:
        return ValidationException(message="Referenced record does not exist or cannot be modified.")
    if "check constraint" in err_str or "ck_" in err_str:
        return ValidationException(message="Submitted values violate validation constraints.")
    return ConflictException(message="Database integrity constraint violated.")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        content = {
            "error": {
                "code": exc.code,
                "message": exc.message,
                "fields": [f.model_dump() for f in exc.fields] if exc.fields else None,
                "request_id": request_id,
            }
        }
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        app_exc = translate_database_error(exc)
        return await app_exception_handler(request, app_exc)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        code_map = {
            404: "NOT_FOUND",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            405: "METHOD_NOT_ALLOWED",
            429: "RATE_LIMITED",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "An error occurred"
        content = {
            "error": {
                "code": code,
                "message": message,
                "fields": None,
                "request_id": request_id,
            }
        }
        headers = dict(exc.headers) if exc.headers else None
        return JSONResponse(status_code=exc.status_code, content=content, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        field_errors = []
        for error in exc.errors():
            loc = ".".join(str(l) for l in error.get("loc", []) if l != "body")
            field_errors.append({"path": loc or "root", "message": error.get("msg", "Invalid input")})

        content = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Input validation failed",
                "fields": field_errors,
                "request_id": request_id,
            }
        }
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, content=content)

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        # Never leak raw stack traces or database errors in responses
        content = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please try again later.",
                "fields": None,
                "request_id": request_id,
            }
        }
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=content)
