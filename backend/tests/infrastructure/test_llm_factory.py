from unittest.mock import MagicMock, patch

import pytest

from backend.core.models.domain import ModelConfigurationRequest, ModelProvider
from backend.infrastructure.llm.factory import configure_model, list_ollama_models


@patch("backend.infrastructure.llm.factory.Ollama")
@patch("backend.infrastructure.llm.factory.Settings")
def test_configure_local_model_updates_active_runtime(
    mock_settings: MagicMock, mock_ollama: MagicMock
) -> None:
    response = configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.OLLAMA,
            model_name="gemma3:12b",
            base_url="http://localhost:11434/",
        )
    )
    mock_ollama.assert_called_once_with(
        model="gemma3:12b",
        base_url="http://localhost:11434",
        request_timeout=120.0,
    )
    assert mock_settings.llm is mock_ollama.return_value
    assert response.model_name == "gemma3:12b"
    assert response.provider is ModelProvider.OLLAMA


@patch("backend.infrastructure.llm.factory.OpenAILike")
@patch("backend.infrastructure.llm.factory.Settings")
def test_configure_api_model_keeps_secret_out_of_response(
    mock_settings: MagicMock, mock_openai: MagicMock
) -> None:
    response = configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.API,
            model_name="google/gemma-4-26b-a4b-it",
            base_url="https://openrouter.ai/api/v1",
            api_key="secret-key",
        )
    )
    assert mock_settings.llm is mock_openai.return_value
    assert response.api_key_configured is True
    assert not hasattr(response, "api_key")


@patch("backend.infrastructure.llm.factory.httpx.get")
def test_list_ollama_models_returns_installed_models(mock_get: MagicMock) -> None:
    mock_get.return_value.json.return_value = {
        "models": [{"name": "gemma3:12b", "size": 123}, {"name": "qwen3:14b"}]
    }
    models = list_ollama_models("http://127.0.0.1:11434")
    assert [model.name for model in models] == ["gemma3:12b", "qwen3:14b"]
    mock_get.return_value.raise_for_status.assert_called_once()


def test_ollama_rejects_non_local_service() -> None:
    with pytest.raises(ValueError, match="loopback"):
        list_ollama_models("https://remote.example")
