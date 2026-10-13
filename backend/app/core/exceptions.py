from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import logger


class AppError(Exception):
    """Base application error with a stable machine-readable code."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "app_error",
        status_code: int = 400,
        details: Any = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str, *, code: str = "not_found", details: Any = None) -> None:
        super().__init__(message, code=code, status_code=404, details=details)


class ConflictError(AppError):
    def __init__(self, message: str, *, code: str = "conflict", details: Any = None) -> None:
        super().__init__(message, code=code, status_code=409, details=details)


class ForbiddenError(AppError):
    def __init__(self, message: str, *, code: str = "forbidden", details: Any = None) -> None:
        super().__init__(message, code=code, status_code=403, details=details)


class ValidationFailed(AppError):
    def __init__(self, message: str, *, code: str = "validation_error", details: Any = None) -> None:
        super().__init__(message, code=code, status_code=422, details=details)


def _error_body(code: str, message: str, details: Any = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "validation_error",
                "Request validation failed.",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        content = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("http_error", content),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content=_error_body("internal_error", "An unexpected error occurred."),
        )


__all__ = [
    "AppError",
    "NotFoundError",
    "ConflictError",
    "ForbiddenError",
    "ValidationFailed",
    "register_exception_handlers",
]