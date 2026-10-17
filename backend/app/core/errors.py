"""Application error types and the single JSON error envelope returned to clients.

Every error response has the shape::

    {"error": {"code": "...", "message": "...", "request_id": "...", "details": {...}}}

Stack traces are logged server-side only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("papertrail.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        if code:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class StorageError(AppError):
    status_code = 502
    code = "storage_error"


class DatabaseError(AppError):
    status_code = 503
    code = "database_error"


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _envelope(request: Request, status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    body: dict[str, Any] = {"error": {"code": code, "message": message, "request_id": _request_id(request)}}
    if details:
        body["error"]["details"] = details
    return JSONResponse(status_code=status, content=body)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.warning("request_id=%s %s: %s", _request_id(request), exc.code, exc.message)
        return _envelope(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [
            {"location": ".".join(str(p) for p in err.get("loc", [])), "message": err.get("msg", "Invalid value")}
            for err in exc.errors()
        ]
        return _envelope(request, 422, "validation_failed", "The request is invalid.", {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _envelope(request, exc.status_code, "http_error", message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error request_id=%s", _request_id(request))
        return _envelope(request, 500, "internal_error", "An unexpected error occurred. Please try again.")
