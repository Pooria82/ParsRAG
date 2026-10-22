"""Server-Sent Events framing for streamed answers.

Errors after the response has started cannot change the HTTP status, so they
are sent as an ``error`` event with the same ``{"detail", "code"}`` body the
JSON endpoints use. A ``ping`` event is sent whenever nothing else was sent for
a while, so the browser can tell a slow answer from a dead connection.
"""

import contextvars
import json
import logging
import queue
import threading
from collections.abc import Generator, Iterator
from typing import Any

from backend.api.errors import MODEL_FAILURE_DETAIL
from backend.core.domain.exceptions import ApplicationError, ParsRAGError
from backend.core.use_case.query.answer_query import QueryEvent
from backend.infrastructure.llm.failures import classify_model_failure

logger = logging.getLogger("backend.main")

# Seconds without an event before a ping is sent. The browser gives up after
# several missed pings, however long the model takes to start answering.
HEARTBEAT_SECONDS = 15.0
_END = object()


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
    logger.error("Unhandled error during stream", exc_info=exc)
    return sse(
        "error",
        {"detail": "An internal server error occurred.", "code": "internal_error"},
    )


def _read_events(
    events: Iterator[QueryEvent], items: queue.Queue[object], stopped: threading.Event
) -> None:
    """Queue each event (or the failure), then close ``events`` and mark the end."""
    try:
        for event in events:
            if stopped.is_set():
                break
            items.put(event)
    except Exception as exc:  # noqa: BLE001 - reported to the client as an event.
        items.put(exc)
    finally:
        close = getattr(events, "close", None)
        if close is not None:
            close()
        items.put(_END)


def event_stream(
    events: Iterator[QueryEvent], heartbeat_seconds: float = HEARTBEAT_SECONDS
) -> Generator[str, None, None]:
    """Frame use-case events as SSE and end with an error event on failure.

    ``events`` is read on its own thread so a ping can be sent while it waits
    (rewriting the question, retrieving, or before the model's first token).
    Closing this generator (client disconnect) stops that thread at the next
    event and closes ``events``, which stops generation and frees the query
    slot.
    """
    items: queue.Queue[object] = queue.Queue()
    stopped = threading.Event()
    context = contextvars.copy_context()
    threading.Thread(
        target=context.run,
        args=(_read_events, events, items, stopped),
        name="answer-stream",
        daemon=True,
    ).start()
    try:
        while True:
            try:
                item = items.get(timeout=heartbeat_seconds)
            except queue.Empty:
                yield sse("ping", {})
                continue
            if item is _END:
                return
            if isinstance(item, Exception):
                yield error_event(item)
            elif isinstance(item, QueryEvent):
                yield sse(item.kind, item.data)
    finally:
        stopped.set()
