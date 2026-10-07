"""Server-Sent Events framing for streamed answers.

Errors after the response has started cannot change the HTTP status, so they
are sent as an ``error`` event with the same ``{"detail", "code"}`` body the
JSON endpoints use.
"""

import json
import logging
from collections.abc import Iterator
from typing import Any

from backend.api.errors import MODEL_FAILURE_DETAIL
from backend.core.domain.exceptions import ApplicationError, ParsRAGError
from backend.core.use_case.query.answer_query import QueryEvent
from backend.infrastructure.llm.failures import classify_model_failure

logger = logging.getLogger("backend.main")


def sse(kind: str, data: Any) -> str:
    """Format one event; JSON keeps newlines inside a single data line."""
    return f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def error_event(exc: Exception) -> str:
    """Describe a failure that happened after streaming started."""
    if isinstance(exc, ApplicationError):
        return sse("error", {"detail": exc.detail, "code": exc.code})
    failure = classify_model_failure(exc)
    if failure is not None:
        logger.warning("Model request failed during stream: %s", type(exc).__name__)
        code = failure[1]
        return sse("error", {"detail": MODEL_FAILURE_DETAIL[code], "code": code})
    if isinstance(exc, ParsRAGError):
        logger.error("ParsRAG Domain Error during stream: %s", exc)
        return sse(
            "error",
            {"detail": "A service error occurred. Please try again.", "code": exc.code},
        )
    logger.exception("Unhandled error during stream")
    return sse(
        "error",
        {"detail": "An internal server error occurred.", "code": "internal_error"},
    )


def event_stream(events: Iterator[QueryEvent]) -> Iterator[str]:
    """Frame use-case events as SSE and end with an error event on failure."""
    try:
        for event in events:
            yield sse(event.kind, event.data)
    except Exception as exc:  # noqa: BLE001 - reported to the client as an event.
        yield error_event(exc)
