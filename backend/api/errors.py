"""Translate core errors into safe HTTP responses.

Every error body has the shape ``{"detail": str, "code": str}``. ``code`` is
a stable identifier the browser maps to a translated, actionable message.
"""

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
    VectorDBConnectionError,
)
from backend.infrastructure.llm.failures import (
    MODEL_CLIENT_ERRORS,
    classify_model_failure,
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

MODEL_FAILURE_DETAIL = {
    "model_timeout": "The model did not answer in time.",
    "model_auth": "The model service rejected the API key.",
    "model_rate_limited": "The model service is rate-limiting requests.",
    "model_not_found": "The configured model was not found on the model service.",
    "model_unavailable": "The model service could not be reached.",
    "model_rejected": "The model service rejected the request.",
}


def error_body(detail: object, code: str) -> dict[str, object]:
    """Build the uniform error payload."""
    return {"detail": detail, "code": code}


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
    return JSONResponse(
        status_code=status_for(exc), content=error_body(exc.detail, exc.code)
    )


async def empty_document_handler(request: Request, exc: Exception) -> JSONResponse:
    """Report documents without extractable text as client errors."""
    logger.warning("EmptyDocumentError: %s", exc)
    code = exc.code if isinstance(exc, EmptyDocumentError) else "empty_document"
    return JSONResponse(status_code=400, content=error_body(str(exc), code))


async def parsrag_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Hide infrastructure failure details behind a coded service error."""
    logger.error("ParsRAG Domain Error: %s", exc)
    failure = classify_model_failure(exc)
    if failure is not None:
        return _model_failure_response(*failure)
    if isinstance(exc, VectorDBConnectionError):
        return JSONResponse(
            status_code=503,
            content=error_body(
                "The vector database is unavailable. Please try again later.",
                exc.code,
            ),
        )
    code = exc.code if isinstance(exc, ParsRAGError) else "service_error"
    return JSONResponse(
        status_code=500,
        content=error_body(
            "A database or service error occurred. Please try again later.", code
        ),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map model-client failures; hide everything else to prevent leaks."""
    failure = classify_model_failure(exc)
    if failure is not None:
        logger.warning("Model request failed: %s", type(exc).__name__)
        return _model_failure_response(*failure)
    logger.exception("Unhandled Server Error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=error_body("An internal server error occurred.", "internal_error"),
    )


def _model_failure_response(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content=error_body(MODEL_FAILURE_DETAIL[code], code)
    )


async def model_failure_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer model-client errors with their specific, actionable code."""
    failure = classify_model_failure(exc)
    if failure is None:
        return await unhandled_error_handler(request, exc)
    logger.warning("Model request failed: %s", type(exc).__name__)
    return _model_failure_response(*failure)


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers; Starlette dispatches on the most specific error type."""
    app.add_exception_handler(ApplicationError, application_error_handler)
    app.add_exception_handler(EmptyDocumentError, empty_document_handler)
    app.add_exception_handler(ParsRAGError, parsrag_error_handler)
    for model_error in MODEL_CLIENT_ERRORS:
        app.add_exception_handler(model_error, model_failure_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
