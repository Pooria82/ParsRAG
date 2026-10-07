"""Model-client exceptions map to stable, actionable error codes."""

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from ollama import ResponseError

from backend.api.dependencies import get_answer_query
from backend.infrastructure.llm.failures import classify_model_failure
from backend.main import app

REQUEST = httpx.Request("POST", "https://models.example/v1/chat/completions")


def _status_error(status: int) -> openai.APIStatusError:
    response = httpx.Response(status, request=REQUEST)
    return openai.APIStatusError("failed", response=response, body=None)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (openai.APITimeoutError(request=REQUEST), (504, "model_timeout")),
        (httpx.ReadTimeout("slow", request=REQUEST), (504, "model_timeout")),
        (_status_error(401), (502, "model_auth")),
        (_status_error(403), (502, "model_auth")),
        (_status_error(404), (502, "model_not_found")),
        (_status_error(429), (503, "model_rate_limited")),
        (_status_error(500), (502, "model_unavailable")),
        (_status_error(400), (502, "model_rejected")),
        (openai.APIConnectionError(request=REQUEST), (502, "model_unavailable")),
        (httpx.ConnectError("refused", request=REQUEST), (502, "model_unavailable")),
        (ResponseError("model 'x' not found", 404), (502, "model_not_found")),
        (ResponseError("overloaded", 503), (502, "model_unavailable")),
        (ConnectionRefusedError(), (502, "model_unavailable")),
        (ValueError("bug"), None),
    ],
)
def test_model_failures_are_classified(
    error: BaseException, expected: tuple[int, str] | None
) -> None:
    assert classify_model_failure(error) == expected


def test_wrapped_failures_are_found_in_the_cause_chain() -> None:
    try:
        try:
            raise _status_error(401)
        except openai.APIStatusError as inner:
            raise RuntimeError("llm call failed") from inner
    except RuntimeError as outer:
        assert classify_model_failure(outer) == (502, "model_auth")


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (openai.APITimeoutError(request=REQUEST), 504, "model_timeout"),
        (_status_error(401), 502, "model_auth"),
        (TimeoutError(), 504, "model_timeout"),
    ],
)
def test_query_route_returns_the_specific_model_failure(
    error: BaseException, status: int, code: str
) -> None:
    """The browser receives a code it can explain, not a generic 500."""

    class FailingUseCase:
        def execute(self, request: object) -> object:
            raise error

    app.dependency_overrides[get_answer_query] = lambda: FailingUseCase()
    try:
        response = TestClient(app).post(
            "/query", json={"prompt": "سلام", "mode": "llm-only"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == status
    assert response.json()["code"] == code
