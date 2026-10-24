"""The sidebar's "ready" needs the model service to answer, not only the app."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.core.domain.enums import ModelProvider
from backend.core.dto.input.model import ModelConfigurationRequest
from backend.core.dto.output.model import OllamaModel
from backend.infrastructure.llm import factory

Activate = Callable[..., None]


@pytest.fixture
def active(monkeypatch: pytest.MonkeyPatch) -> Activate:
    """Set the active connection and forget cached checks."""

    def use(provider: ModelProvider, model: str, key: str | None = None) -> None:
        base = (
            "http://localhost:11434"
            if provider is ModelProvider.OLLAMA
            else "https://api.example.com/v1"
        )
        monkeypatch.setattr(
            factory,
            "_configuration",
            ModelConfigurationRequest(
                provider=provider, model_name=model, base_url=base
            ),
        )
        monkeypatch.setattr(factory, "_api_key", key)
        monkeypatch.setattr(
            factory, "_api_keys", {factory._origin(base): key} if key else {}
        )
        monkeypatch.setattr(factory, "model_api_is_external", lambda url: True)
        monkeypatch.setattr(factory, "_status_cache", None)

    return use


def test_ollama_that_is_not_running_is_unreachable(active: Activate) -> None:
    active(ModelProvider.OLLAMA, "gemma3:4b")
    with patch.object(
        factory, "list_ollama_models", side_effect=httpx.ConnectError("refused")
    ):
        assert factory.model_connection_status().status == "unreachable"


def test_ollama_without_the_selected_model_is_reported(active: Activate) -> None:
    active(ModelProvider.OLLAMA, "gemma3:4b")
    with patch.object(
        factory, "list_ollama_models", return_value=[OllamaModel(name="qwen2.5:7b")]
    ):
        assert factory.model_connection_status().status == "model_missing"
    active(ModelProvider.OLLAMA, "gemma3")
    with patch.object(
        factory, "list_ollama_models", return_value=[OllamaModel(name="gemma3:latest")]
    ):
        assert factory.model_connection_status().status == "ready"


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        (200, "ready"),
        (404, "ready"),
        (401, "auth_failed"),
        (403, "auth_failed"),
        (503, "unreachable"),
    ],
)
def test_api_answers_map_to_a_status(
    active: Activate, answer: int, expected: str
) -> None:
    active(ModelProvider.API, "google/gemma", key="secret")
    client = MagicMock()
    client.__enter__.return_value.get.return_value = httpx.Response(answer)
    with patch.object(factory, "guarded_http_client", return_value=client):
        assert factory.model_connection_status().status == expected
    headers = client.__enter__.return_value.get.call_args.kwargs["headers"]
    assert headers == {"Authorization": "Bearer secret"}


def test_an_unreachable_api_is_reported(active: Activate) -> None:
    active(ModelProvider.API, "google/gemma", key="secret")
    client = MagicMock()
    client.__enter__.return_value.get.side_effect = httpx.ConnectTimeout("timeout")
    with patch.object(factory, "guarded_http_client", return_value=client):
        assert factory.model_connection_status().status == "unreachable"


def test_a_recent_check_is_reused(active: Activate) -> None:
    active(ModelProvider.OLLAMA, "gemma3:4b")
    now = [100.0]
    with patch.object(
        factory, "list_ollama_models", side_effect=httpx.ConnectError("x")
    ) as check:
        factory.model_connection_status(clock=lambda: now[0])
        now[0] += 5
        factory.model_connection_status(clock=lambda: now[0])
        assert check.call_count == 1
        now[0] += factory.MODEL_STATUS_TTL_SECONDS
        factory.model_connection_status(clock=lambda: now[0])
        assert check.call_count == 2


def test_the_route_reports_the_status() -> None:
    from fastapi.testclient import TestClient

    from backend.main import app

    with (
        patch.object(factory, "_check_connection", return_value="unreachable"),
        patch.object(factory, "_status_cache", None),
    ):
        body = TestClient(app).get("/models/status").json()
    assert body["status"] == "unreachable"


def test_an_external_api_without_a_key_is_reported_without_asking_it(
    active: Activate,
) -> None:
    """OpenRouter lists models without a key; questions would still fail."""
    active(ModelProvider.API, "google/gemma")
    with (
        patch.object(factory, "model_api_is_external", return_value=True),
        patch.object(factory, "guarded_http_client") as client,
    ):
        assert factory.model_connection_status().status == "key_missing"
    client.assert_not_called()


def test_a_missing_key_is_named_when_a_question_fails() -> None:
    import openai

    from backend.infrastructure.llm.failures import classify_model_failure

    error = openai.OpenAIError("Missing credentials. Please pass an `api_key`.")
    assert classify_model_failure(error) == (502, "model_key_missing")
