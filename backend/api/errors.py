"""Translate core errors into safe HTTP responses."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.core.domain.exceptions import (
    ApplicationError,
    CapacityExceededError,
    ConflictError,
    EmptyDocumentError,
    InvalidInputError,
    NotFoundError,
    ParsRAGError,
    PayloadTooLargeError,
    UpstreamServiceError,
)

logger = logging.getLogger("backend.main")

APPLICATION_ERROR_STATUS: dict[type[ApplicationError], int] = {
    InvalidInputError: 400,
    NotFoundError: 404,
    ConflictError: 409,
    PayloadTooLargeError: 413,
    CapacityExceededError: 429,
    UpstreamServiceError: 502,
}


def status_for(error: ApplicationError) -> int:
    """Return the HTTP status for an application error, defaulting to 400."""
    for error_type, status_code in APPLICATION_ERROR_STATUS.items():
        if isinstance(error, error_type):
            return status_code
    return 400


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return the use case's caller-safe detail with its mapped status."""
    if not isinstance(exc, ApplicationError):
        return await unhandled_error_handler(request, exc)
    return JSONResponse(status_code=status_for(exc), content={"detail": exc.detail})


async def empty_document_handler(request: Request, exc: Exception) -> JSONResponse:
    """Report documents without extractable text as client errors."""
    logger.warning("EmptyDocumentError: %s", exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


async def parsrag_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Hide infrastructure failure details behind a generic service error."""
    logger.error("ParsRAG Domain Error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "A database or service error occurred. Please try again later."
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch every unhandled exception to prevent stack trace leaks."""
    logger.exception("Unhandled Server Error: %s", exc)
    return JSONResponse(
        status_code=500, content={"detail": "An internal server error occurred."}
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers; Starlette dispatches on the most specific error type."""
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(EmptyDocumentError, empty_document_handler)
    app.add_exception_handler(ParsRAGError, parsrag_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
