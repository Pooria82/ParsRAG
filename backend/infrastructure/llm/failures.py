"""Classify model-client exceptions into stable, user-actionable codes.

LlamaIndex surfaces errors from the OpenAI SDK, httpx, and the Ollama client
unchanged. The HTTP adapter uses this mapping so a user sees "the API key was
rejected" or "the model timed out" instead of a generic server error.
"""

from __future__ import annotations

import httpx
import openai
from ollama import ResponseError as OllamaResponseError

# Exception types raised by the model clients LlamaIndex wraps.
MODEL_CLIENT_ERRORS: tuple[type[Exception], ...] = (
    openai.OpenAIError,
    httpx.HTTPError,
    OllamaResponseError,
    TimeoutError,
    ConnectionError,
)

# (HTTP status, code) pairs returned to the browser.
MODEL_TIMEOUT = (504, "model_timeout")
MODEL_AUTH = (502, "model_auth")
MODEL_RATE_LIMITED = (503, "model_rate_limited")
MODEL_NOT_FOUND = (502, "model_not_found")
MODEL_UNAVAILABLE = (502, "model_unavailable")
MODEL_REJECTED = (502, "model_rejected")


def _status_failure(status: int) -> tuple[int, str]:
    if status in {401, 403}:
        return MODEL_AUTH
    if status == 404:
        return MODEL_NOT_FOUND
    if status == 429:
        return MODEL_RATE_LIMITED
    if status >= 500:
        return MODEL_UNAVAILABLE
    return MODEL_REJECTED


def _classify_one(error: BaseException) -> tuple[int, str] | None:
    if isinstance(
        error, openai.APITimeoutError | httpx.TimeoutException | TimeoutError
    ):
        return MODEL_TIMEOUT
    if isinstance(error, openai.APIStatusError):
        return _status_failure(error.status_code)
    if isinstance(error, openai.APIConnectionError | httpx.TransportError):
        return MODEL_UNAVAILABLE
    if isinstance(error, httpx.HTTPStatusError):
        return _status_failure(error.response.status_code)
    if isinstance(error, OllamaResponseError):
        if "not found" in str(error).lower():
            return MODEL_NOT_FOUND
        return _status_failure(error.status_code)
    if isinstance(error, ConnectionError):
        return MODEL_UNAVAILABLE
    return None


def classify_model_failure(error: BaseException) -> tuple[int, str] | None:
    """Return (status, code) for a model failure anywhere in the cause chain."""
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        failure = _classify_one(current)
        if failure is not None:
            return failure
        current = current.__cause__ or current.__context__
    return None
