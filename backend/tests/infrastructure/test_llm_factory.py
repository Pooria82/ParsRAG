from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.core.domain.enums import ModelProvider
from backend.core.dto.input.model import ModelConfigurationRequest
from backend.infrastructure.llm.endpoint_policy import (
    OllamaURLNotAllowedError,
    allowed_ollama_hosts,
    is_allowed_ollama_url,
)
from backend.infrastructure.llm.factory import (
    condensing_llm,
    configure_model,
    generate_conversation_title,
    get_model_configuration,
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
def test_ollama_receives_the_configured_context_length(
    mock_settings: MagicMock, mock_ollama: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """num_ctx follows OLLAMA_CONTEXT_LENGTH instead of the model maximum."""
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "2048")
    monkeypatch.setenv("LLM_REQUEST_TIMEOUT_SECONDS", "90")
    configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.OLLAMA,
            model_name="gemma3:12b",
            base_url="http://localhost:11434",
        ),
        verify=False,
        persist=False,
    )
    assert mock_ollama.call_args_list[0].kwargs["context_window"] == 2048
    assert mock_ollama.call_args_list[0].kwargs["request_timeout"] == 90.0


@patch("backend.infrastructure.llm.factory.ReasoningFreeOpenAILike")
@patch("backend.infrastructure.llm.factory.Settings")
def test_api_requests_stay_within_the_browser_timeout(
    mock_settings: MagicMock, mock_openai: MagicMock
) -> None:
    """Answer (two attempts) plus rewrite fit in the client's 330 s window."""
    configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.API,
            model_name="api-model",
            base_url="https://127.0.0.1/v1",
            api_key="key",
        ),
        verify=False,
        persist=False,
    )
    answer, condense = (call.kwargs for call in mock_openai.call_args_list)
    worst_case = answer["timeout"] * (answer["max_retries"] + 1) + condense[
        "timeout"
    ] * (condense["max_retries"] + 1)
    assert worst_case < 330
    assert answer["context_window"] == 32768
    assert condensing_llm() is mock_openai.return_value


@patch("backend.infrastructure.llm.factory.Ollama")
@patch("backend.infrastructure.llm.factory.Settings")
def test_configure_local_model_updates_active_runtime(
    mock_settings: MagicMock, mock_ollama: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OLLAMA_CONTEXT_LENGTH", raising=False)
    monkeypatch.delenv("OLLAMA_THINK", raising=False)
    response = configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.OLLAMA,
            model_name="gemma3:12b",
            base_url="http://localhost:11434/",
        ),
        verify=False,
        persist=False,
    )
    answer_call, condense_call = mock_ollama.call_args_list
    assert answer_call.kwargs == {
        "model": "gemma3:12b",
        "base_url": "http://localhost:11434",
        "request_timeout": 120.0,
        "context_window": 8192,
        "thinking": False,
    }
    assert condense_call.kwargs["request_timeout"] == 30.0
    assert mock_settings.llm is mock_ollama.return_value
    assert response.model_name == "gemma3:12b"
    assert response.provider is ModelProvider.OLLAMA


@patch("backend.infrastructure.llm.factory.ReasoningFreeOpenAILike")
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
@patch("backend.infrastructure.llm.factory.ReasoningFreeOpenAILike")
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
    monkeypatch.setattr(factory, "_api_keys", {})
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


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434",
        "http://127.0.0.1:11434/",
        "http://[::1]:11434",
        "http://ollama:11434",
        "http://host.docker.internal:11434",
        "http://HOST.DOCKER.INTERNAL:11434",
    ],
)
def test_ollama_accepts_loopback_compose_and_docker_host(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The host's own Ollama is reachable from Docker without extra settings."""
    monkeypatch.delenv("OLLAMA_INTERNAL_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_ALLOWED_HOSTS", raising=False)
    assert is_allowed_ollama_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://remote.example",
        "http://remote.example:11434",
        "https://host.docker.internal:11434",
        "http://ollama.example:11434",
        "http://user@localhost:11434",
        "http://user:secret@host.docker.internal:11434",
        "http://localhost:11434/api/tags",
        "http://localhost:11434?redirect=remote",
        "http://localhost:11434#fragment",
        "http://localhost:not-a-port",
        "ftp://localhost:11434",
        "http://192.168.1.10:11434",
    ],
)
def test_ollama_rejects_other_hosts_schemes_credentials_and_paths(
    url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Arbitrary hosts, HTTPS, credentials, and paths cannot disguise a target."""
    monkeypatch.delenv("OLLAMA_INTERNAL_HOST", raising=False)
    monkeypatch.delenv("OLLAMA_ALLOWED_HOSTS", raising=False)
    assert not is_allowed_ollama_url(url)
    with pytest.raises(OllamaURLNotAllowedError, match="OLLAMA_ALLOWED_HOSTS"):
        list_ollama_models(url)


def test_allowed_hosts_are_extended_by_the_operator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comma-separated additions and the legacy single host are both honored."""
    monkeypatch.setenv("OLLAMA_ALLOWED_HOSTS", " gpu-box , 172.17.0.1,, [fd00::1] ")
    monkeypatch.setenv("OLLAMA_INTERNAL_HOST", "Legacy-Ollama")

    hosts = allowed_ollama_hosts()

    assert {"gpu-box", "172.17.0.1", "fd00::1", "legacy-ollama"} <= hosts
    assert "" not in hosts
    assert is_allowed_ollama_url("http://gpu-box:11434")
    assert is_allowed_ollama_url("http://172.17.0.1:11434")
    assert is_allowed_ollama_url("http://[fd00::1]:11434")
    assert is_allowed_ollama_url("http://legacy-ollama:11434")
    assert not is_allowed_ollama_url("http://gpu-box.example:11434")


@patch("backend.infrastructure.llm.factory.httpx.get")
def test_list_ollama_models_reads_the_docker_host(mock_get: MagicMock) -> None:
    mock_get.return_value.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}

    models = list_ollama_models("http://host.docker.internal:11434/")

    assert [model.name for model in models] == ["qwen2.5:7b"]
    assert mock_get.call_args.args[0] == "http://host.docker.internal:11434/api/tags"


@patch("backend.infrastructure.llm.factory.save_model_configuration")
@patch("backend.infrastructure.llm.factory.httpx.get")
@patch("backend.infrastructure.llm.factory.Ollama")
@patch("backend.infrastructure.llm.factory.Settings")
def test_configuring_the_docker_host_ollama_is_verified_and_saved(
    mock_settings: MagicMock,
    mock_ollama: MagicMock,
    mock_get: MagicMock,
    mock_save: MagicMock,
) -> None:
    mock_get.return_value.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}

    result = configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.OLLAMA,
            model_name="qwen2.5:7b",
            base_url="http://host.docker.internal:11434/",
        )
    )

    assert result.base_url == "http://host.docker.internal:11434"
    assert (
        mock_ollama.call_args.kwargs["base_url"] == "http://host.docker.internal:11434"
    )
    assert mock_save.call_args.args[0].base_url == "http://host.docker.internal:11434"


@patch("backend.infrastructure.llm.factory.save_model_configuration")
@patch("backend.infrastructure.llm.factory.Settings")
def test_disallowed_ollama_url_is_never_saved(
    mock_settings: MagicMock, mock_save: MagicMock
) -> None:
    with pytest.raises(OllamaURLNotAllowedError):
        configure_model(
            ModelConfigurationRequest(
                provider=ModelProvider.OLLAMA,
                model_name="m",
                base_url="http://attacker.example:11434",
            )
        )
    mock_save.assert_not_called()


def test_configuration_reports_the_server_ollama_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434/")
    assert get_model_configuration().ollama_base_url == (
        "http://host.docker.internal:11434"
    )


@patch("backend.infrastructure.llm.factory.Ollama")
@patch("backend.infrastructure.llm.factory.ReasoningFreeOpenAILike")
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
    assert mock_settings.llm.complete.call_args.kwargs == {"max_tokens": 1024}


@pytest.mark.parametrize(
    ("value", "expected"), [(None, False), ("0", False), ("1", True)]
)
@patch("backend.infrastructure.llm.factory.Ollama")
@patch("backend.infrastructure.llm.factory.Settings")
def test_ollama_thinking_is_off_unless_enabled(
    mock_settings: MagicMock,
    mock_ollama: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
    expected: bool,
) -> None:
    """Thinking models would otherwise spend the answer budget on reasoning."""
    if value is None:
        monkeypatch.delenv("OLLAMA_THINK", raising=False)
    else:
        monkeypatch.setenv("OLLAMA_THINK", value)

    configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.OLLAMA,
            model_name="qwen3.5:4b",
            base_url="http://host.docker.internal:11434",
        ),
        verify=False,
        persist=False,
    )

    answer_call, condense_call = mock_ollama.call_args_list
    assert answer_call.kwargs["thinking"] is expected
    assert condense_call.kwargs["thinking"] is expected


@patch("backend.infrastructure.llm.factory.Settings")
@patch("backend.infrastructure.llm.factory.ReasoningFreeOpenAILike")
@patch("backend.infrastructure.llm.factory.httpx.get")
def test_a_stored_key_is_not_sent_to_a_different_server(
    mock_get: MagicMock,
    mock_openai: MagicMock,
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing the API address without a key must not leak the old key."""
    import backend.infrastructure.llm.factory as factory

    monkeypatch.setattr(factory, "_api_keys", {})
    first = ModelConfigurationRequest(
        provider=ModelProvider.API,
        model_name="m",
        base_url="https://openrouter.ai/api/v1",
        api_key="openrouter-key",
        disclosure_acknowledged=True,
    )
    with patch("backend.infrastructure.llm.endpoint_policy.socket.getaddrinfo") as dns:
        dns.return_value = [(None, None, None, None, ("104.18.2.115", 443))]
        configure_model(first, persist=False)
        calls = mock_get.call_count
        # Without a key for that host it is refused, and the old key is not sent.
        with pytest.raises(factory.APIKeyMissingError, match=r"other.example"):
            configure_model(
                first.model_copy(
                    update={"base_url": "https://other.example/v1", "api_key": None}
                ),
                persist=False,
            )
        assert mock_get.call_count == calls
        assert all(
            call.kwargs.get("api_base") != "https://other.example/v1"
            for call in mock_openai.call_args_list
        )

        configure_model(first.model_copy(update={"api_key": None}), persist=False)
    assert mock_get.call_args.kwargs["headers"] == {
        "Authorization": "Bearer openrouter-key"
    }


@patch("backend.infrastructure.llm.factory.Settings")
@patch("backend.infrastructure.llm.factory.ReasoningFreeOpenAILike")
@patch("backend.infrastructure.llm.factory.httpx.get")
def test_the_sdk_does_not_retry_on_top_of_status_retries(
    mock_get: MagicMock, mock_openai: MagicMock, mock_settings: MagicMock
) -> None:
    configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.API,
            model_name="m",
            base_url="https://127.0.0.1/v1",
            api_key="k",
        ),
        persist=False,
    )

    answer_client = mock_openai.call_args_list[0].kwargs
    assert answer_client["max_retries"] == 0
    assert answer_client["status_retries"] >= 1


def test_ollama_titles_are_capped_with_num_predict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ollama ignores max_tokens, so the cap is passed as its num_predict option."""
    from llama_index.core import Settings
    from llama_index.llms.ollama import Ollama  # type: ignore[import-untyped]

    import backend.infrastructure.llm.factory as factory

    seen: list[dict[str, object]] = []

    def complete(self: Ollama, prompt: str, **kwargs: object) -> str:
        seen.append(dict(self.additional_kwargs))
        return "Project timeline"

    monkeypatch.setattr(Ollama, "complete", complete)
    llm = Ollama(model="gemma3:4b", base_url="http://127.0.0.1:11434")
    monkeypatch.setattr(Settings, "_llm", llm)

    assert factory.generate_conversation_title("when is the deadline?", "en") == (
        "Project timeline"
    )
    assert seen == [{"num_predict": factory._SHORT_ANSWER_TOKENS}]
    assert "num_predict" not in llm.additional_kwargs


@patch("backend.infrastructure.llm.factory.Settings")
@patch("backend.infrastructure.llm.factory.ReasoningFreeOpenAILike")
@patch("backend.infrastructure.llm.factory.httpx.get")
def test_api_models_use_the_guarded_http_client(
    mock_get: MagicMock, mock_openai: MagicMock, mock_settings: MagicMock
) -> None:
    from backend.infrastructure.llm.endpoint_policy import GuardedTransport

    configure_model(
        ModelConfigurationRequest(
            provider=ModelProvider.API,
            model_name="m",
            base_url="https://127.0.0.1/v1",
            api_key="k",
        ),
        persist=False,
    )

    for call in mock_openai.call_args_list:
        client = call.kwargs["http_client"]
        assert client.follow_redirects is False
        assert isinstance(client._transport, GuardedTransport)


def test_a_saved_connection_to_another_host_starts_without_the_env_key(
    tmp_path: Path,
) -> None:
    """The .env key belongs to MODEL_API_BASE_URL and is never given to OpenRouter."""
    import json
    import os
    import subprocess
    import sys

    saved = tmp_path / "model-configuration.json"
    saved.write_text(
        json.dumps(
            {
                "provider": "api",
                "model_name": "google/gemma-4-26b-a4b-it",
                "base_url": "https://openrouter.ai/api/v1",
                "disclosure_acknowledged": True,
            }
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "MODEL_API_KEY": "google-studio-key",
        "MODEL_API_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "PARSRAG_CONFIG_PATH": str(saved),
    }
    env.pop("OPENROUTER_API_KEY", None)
    script = (
        "from backend.infrastructure.llm import factory as f;"
        "print(f._configuration.api_key);"
        "print(sorted(host for _, host, _ in f._api_keys))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parents[3],
    )
    assert result.stdout.split("\n")[:2] == [
        "None",
        "['generativelanguage.googleapis.com']",
    ]
