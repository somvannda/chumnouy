"""Uniform error envelope.

Every error response is ``{"error": {"code", "message", "details"}}``
(docs/api.md conventions) rather than FastAPI's bare ``{"detail": ...}``.
Installed on the app in ``main.py``.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "too_many_requests",
    500: "internal_error",
    502: "bad_gateway",
}


def error_code(status_code: int) -> str:
    return _STATUS_CODES.get(status_code, "error")


def envelope(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, str):
        message, details = exc.detail, {}
    else:
        message, details = "Request failed", exc.detail
    return JSONResponse(
        envelope(error_code(exc.status_code), message, details),
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        jsonable_encoder(
            envelope("validation_error", "Request validation failed", {"errors": exc.errors()})
        ),
        status_code=422,
    )


def install(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
