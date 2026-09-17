import os
from threading import RLock
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from llama_index.core import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding  # type: ignore
from llama_index.llms.ollama import Ollama  # type: ignore
from llama_index.llms.openai_like import OpenAILike  # type: ignore

from backend.core.models.domain import (
    ModelConfigurationRequest,
    ModelConfigurationResponse,
    ModelProvider,
    OllamaModel,
)

load_dotenv()

_configuration_lock = RLock()
_api_key = os.getenv("OPENROUTER_API_KEY") or None
_configuration = ModelConfigurationRequest(
    provider=ModelProvider.API
    if os.getenv("LLM_PROVIDER", "ollama").lower() in {"api", "openrouter"}
    else ModelProvider.OLLAMA,
    model_name=os.getenv("LLM_MODEL_NAME", "google/gemma-4-26b-a4b-it"),
    base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if os.getenv("LLM_PROVIDER", "ollama").lower() in {"api", "openrouter"}
    else os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    api_key=_api_key,
)


def _is_local_ollama_url(value: str) -> bool:
    """Checks that Ollama stays on the local machine."""
    parsed = urlparse(value)
    return parsed.scheme == "http" and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }


def get_model_configuration() -> ModelConfigurationResponse:
    """Returns the active model settings without returning the API key."""
    with _configuration_lock:
        return ModelConfigurationResponse(
            provider=_configuration.provider,
            model_name=_configuration.model_name,
            base_url=_configuration.base_url,
            api_key_configured=bool(_api_key),
        )


def configure_model(
    configuration: ModelConfigurationRequest,
) -> ModelConfigurationResponse:
    """Applies a validated model connection for subsequent requests."""
    global _api_key, _configuration
    base_url = configuration.base_url.rstrip("/")
    if configuration.provider is ModelProvider.OLLAMA and not _is_local_ollama_url(
        base_url
    ):
        raise ValueError("Ollama must use a local loopback address.")
    if configuration.provider is ModelProvider.API:
        api_key = configuration.api_key or _api_key
        _api_key = api_key
        Settings.llm = OpenAILike(
            model=configuration.model_name,
            api_key=api_key or "",
            api_base=base_url,
            is_chat_model=True,
            timeout=120.0,
            max_retries=3,
        )
        configuration = configuration.model_copy(
            update={"api_key": api_key, "base_url": base_url}
        )
    else:
        Settings.llm = Ollama(
            model=configuration.model_name, base_url=base_url, request_timeout=120.0
        )
        configuration = configuration.model_copy(
            update={"api_key": None, "base_url": base_url}
        )
    with _configuration_lock:
        _configuration = configuration
    return get_model_configuration()


def list_ollama_models(base_url: str) -> list[OllamaModel]:
    """Lists models installed on the configured Ollama service."""
    if not _is_local_ollama_url(base_url):
        raise ValueError("Ollama must use a local loopback address.")
    response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=5.0)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models", []) if isinstance(payload, dict) else []
    return [
        OllamaModel(name=item["name"], size=item.get("size"))
        for item in models
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]


def setup_llm_and_embeddings() -> None:
    """Configures global settings for LLMs and embeddings.

    Sets up the LLM and HuggingFace embeddings in the global LlamaIndex
    Settings object based on environment variables or defaults.
    """
    # LLM Setup
    configure_model(_configuration)

    # Embeddings Setup (using intfloat/multilingual-e5-base)
    embed_model_name = os.getenv("EMBED_MODEL_NAME", "intfloat/multilingual-e5-base")
    Settings.embed_model = HuggingFaceEmbedding(model_name=embed_model_name)
