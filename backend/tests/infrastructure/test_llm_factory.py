from unittest.mock import MagicMock, patch

import pytest

from backend.core.models.domain import ModelConfigurationRequest, ModelProvider
from backend.infrastructure.llm.factory import (
    configure_model,
    generate_conversation_title,
    list_ollama_models,
    resolve_embedding_device,
)


def test_embedding_device_auto_prefers_cuda_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GPU-enabled images move embedding work off system RAM and CPU."""
    monkeypatch.setenv("EMBED_DEVICE", "auto")
    with patch(
        "backend.infrastructure.llm.factory.torch.cuda.is_available", return_value=True
    ):
        assert resolve_embedding_device() == "cuda"


def test_embedding_device_can_be_forced_to_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    """CPU mode stays deterministic even on a GPU host."""
    monkeypatch.setenv("EMBED_DEVICE", "cpu")
    assert resolve_embedding_device() == "cpu"


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
        ),
        verify=False,
        persist=False,
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
            base_url="https://127.0.0.1/v1",
            api_key="secret-key",
        ),
        verify=False,
        persist=False,
    )
    assert mock_settings.llm is mock_openai.return_value
    assert response.api_key_configured is True
    assert not hasattr(response, "api_key")


@patch("backend.infrastructure.llm.factory.Settings")
@patch("backend.infrastructure.llm.factory.OpenAILike")
@patch("backend.infrastructure.llm.factory.httpx.get")
def test_private_api_without_key_is_verified_through_models_endpoint(
    mock_get: MagicMock,
    mock_openai: MagicMock,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A trusted keyless API is verified before its adapter becomes active."""
    import backend.infrastructure.llm.factory as factory

    monkeypatch.setattr(factory, "_api_key", None)
    response = configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.API,
            model_name="corporate-model",
            base_url="https://127.0.0.1/v1",
        ),
        persist=False,
    )

    mock_get.assert_called_once_with(
        "https://127.0.0.1/v1/models",
        headers={},
        timeout=8.0,
        follow_redirects=False,
    )
    mock_get.return_value.raise_for_status.assert_called_once()
    assert mock_openai.call_args.kwargs["api_key"] == ""
    assert mock_settings.llm is mock_openai.return_value
    assert response.api_key_configured is False


@patch("backend.infrastructure.llm.factory.httpx.get")
def test_keyed_api_verification_uses_supplied_secret(mock_get: MagicMock) -> None:
    """The verification request authenticates without persisting or returning its key."""
    from backend.infrastructure.llm.factory import _verify_openai_compatible_connection

    _verify_openai_compatible_connection("https://127.0.0.1/v1", "real-key")
    mock_get.assert_called_once_with(
        "https://127.0.0.1/v1/models",
        headers={"Authorization": "Bearer real-key"},
        timeout=8.0,
        follow_redirects=False,
    )


@patch("backend.infrastructure.llm.factory.model_api_is_external", return_value=True)
def test_external_api_requires_explicit_disclosure(_: MagicMock) -> None:
    """An external endpoint cannot become active from unchecked settings."""
    with pytest.raises(ValueError, match="disclosure"):
        configure_model(
            ModelConfigurationRequest(
                provider=ModelProvider.API,
                model_name="external-model",
                base_url="https://127.0.0.1/v1",
                api_key="secret-key",
            ),
            verify=False,
            persist=False,
        )


def test_environment_disclosure_requires_explicit_operator_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting API provider alone is not external data-sharing consent."""
    from backend.infrastructure.llm.factory import _environment_configuration

    monkeypatch.setenv("LLM_PROVIDER", "api")
    monkeypatch.setenv("MODEL_API_DISCLOSURE_ACKNOWLEDGED", "0")
    assert not _environment_configuration().disclosure_acknowledged
    monkeypatch.setenv("MODEL_API_DISCLOSURE_ACKNOWLEDGED", "1")
    assert _environment_configuration().disclosure_acknowledged


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


@patch("backend.infrastructure.llm.factory.httpx.get")
def test_ollama_accepts_explicit_compose_service(
    mock_get: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact configured Docker hostname is accepted without allowing arbitrary hosts."""
    monkeypatch.setenv("OLLAMA_INTERNAL_HOST", "ollama")
    mock_get.return_value.json.return_value = {"models": []}

    assert list_ollama_models("http://ollama:11434") == []
    with pytest.raises(ValueError, match="configured internal host"):
        list_ollama_models("http://ollama.example:11434")


@pytest.mark.parametrize(
    "url",
    [
        "http://user@localhost:11434",
        "http://localhost:11434/api/tags",
        "http://localhost:11434?redirect=remote",
    ],
)
def test_ollama_rejects_ambiguous_local_urls(url: str) -> None:
    """Credentials, paths, and query strings cannot disguise an Ollama target."""
    with pytest.raises(ValueError, match="loopback"):
        list_ollama_models(url)


@patch("backend.infrastructure.llm.factory.Ollama")
@patch("backend.infrastructure.llm.factory.OpenAILike")
@patch("backend.infrastructure.llm.factory.Settings")
def test_switching_to_ollama_does_not_forget_existing_api_key(
    mock_settings: MagicMock, mock_openai: MagicMock, mock_ollama: MagicMock
) -> None:
    configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.API,
            model_name="api-model",
            base_url="https://127.0.0.1/v1",
            api_key="keep-me",
        ),
        verify=False,
        persist=False,
    )
    local = configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.OLLAMA,
            model_name="local-model",
            base_url="http://localhost:11434",
        ),
        verify=False,
        persist=False,
    )
    assert local.api_key_configured is True
    configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.API,
            model_name="api-model",
            base_url="https://127.0.0.1/v1",
        ),
        verify=False,
        persist=False,
    )
    assert mock_openai.call_args.kwargs["api_key"] == "keep-me"


@patch("backend.infrastructure.llm.factory.Settings")
def test_generated_conversation_title_is_bounded_and_sanitized(
    mock_settings: MagicMock,
) -> None:
    """Only one clean navigation label is returned from model output."""
    mock_settings.llm.complete.return_value = (
        "عنوان: **تحلیل ساختار رمزنگاری فیستل**!\nتوضیح اضافه"
    )

    title = generate_conversation_title("فیستل چیست؟", "fa")

    assert title == "تحلیل ساختار رمزنگاری فیستل"
    prompt = mock_settings.llm.complete.call_args.args[0]
    assert "untrusted topic text" in prompt
    assert '"فیستل چیست؟"' in prompt
    assert mock_settings.llm.complete.call_args.kwargs == {"max_tokens": 32}
