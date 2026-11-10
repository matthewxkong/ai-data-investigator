"""Consistent public errors with safe messages and server-generated request identifiers."""

import logging
import sqlite3
from collections.abc import Awaitable, Callable, Mapping
from http import HTTPStatus
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse, Response

from app.repositories import MetadataNotFoundError

logger = logging.getLogger(__name__)


class ValidationDetail(BaseModel):
    location: list[str | int]
    type: str
    message: str = "Invalid value."


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: list[ValidationDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorBody


class ApiError(Exception):
    """An intentionally public application error; never pass raw exceptions as messages."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[ValidationDetail] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    if not isinstance(request_id, str):
        request_id = uuid4().hex
    body = ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=details or [])
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={**(headers or {}), "X-Request-ID": request_id},
    )


async def http_error_handler(request: Request, exception: Exception) -> JSONResponse:
    assert isinstance(exception, HTTPException)
    try:
        message = HTTPStatus(exception.status_code).phrase
    except ValueError:
        message = "Request failed."
    code = {404: "not_found", 405: "method_not_allowed"}.get(exception.status_code, "http_error")
    return error_response(
        request,
        status_code=exception.status_code,
        code=code,
        message=message,
        headers=exception.headers,
    )


async def validation_error_handler(request: Request, exception: Exception) -> JSONResponse:
    assert isinstance(exception, RequestValidationError)
    details = [
        ValidationDetail(location=list(error["loc"]), type=str(error["type"]))
        for error in exception.errors()
    ]
    return error_response(
        request,
        status_code=422,
        code="validation_error",
        message="The request contains invalid values.",
        details=details,
    )


async def api_error_handler(request: Request, exception: Exception) -> JSONResponse:
    assert isinstance(exception, ApiError)
    return error_response(
        request,
        status_code=exception.status_code,
        code=exception.code,
        message=exception.message,
    )


async def not_found_handler(request: Request, exception: Exception) -> JSONResponse:
    return error_response(request, status_code=404, code="not_found", message="Resource not found.")


async def database_error_handler(request: Request, exception: Exception) -> JSONResponse:
    return error_response(
        request,
        status_code=503,
        code="metadata_unavailable",
        message="Metadata storage is temporarily unavailable.",
    )


async def unexpected_error_handler(request: Request, exception: Exception) -> JSONResponse:
    response = error_response(
        request, status_code=500, code="internal_error", message="An unexpected error occurred."
    )
    logger.error(
        "Unhandled request failure request_id=%s type=%s",
        response.headers["X-Request-ID"],
        type(exception).__name__,
    )
    return response


def install_error_handlers(application: FastAPI) -> None:
    @application.middleware("http")
    async def identify_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = uuid4().hex
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    application.add_exception_handler(HTTPException, http_error_handler)
    application.add_exception_handler(RequestValidationError, validation_error_handler)
    application.add_exception_handler(ApiError, api_error_handler)
    application.add_exception_handler(MetadataNotFoundError, not_found_handler)
    application.add_exception_handler(sqlite3.Error, database_error_handler)
    application.add_exception_handler(Exception, unexpected_error_handler)
