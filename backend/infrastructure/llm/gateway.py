"""``ModelGateway`` adapter over the LlamaIndex model factory."""

from typing import Literal

import httpx

from backend.core.domain.enums import ModelProvider
from backend.core.domain.exceptions import ModelConnectionError, OllamaConnectionError
from backend.core.dto.input.model import ModelConfigurationRequest
from backend.core.dto.output.model import ModelConfigurationResponse, OllamaModel
from backend.infrastructure.llm import factory
from backend.infrastructure.llm.endpoint_policy import OllamaURLNotAllowedError


def _ollama_error(exc: Exception) -> OllamaConnectionError:
    """Name why an Ollama service could not be used."""
    if isinstance(exc, OllamaURLNotAllowedError):
        return OllamaConnectionError(
            "The Ollama URL is not allowed.", "ollama_url_not_allowed"
        )
    return OllamaConnectionError("Ollama could not be reached.", "ollama_unreachable")


class LlamaIndexModelGateway:
    """Expose runtime model management while hiding client-library failures."""

    def current_configuration(self) -> ModelConfigurationResponse:
        """Return the active connection without its API key."""
        return factory.get_model_configuration()

    def configure(
        self, configuration: ModelConfigurationRequest
    ) -> ModelConfigurationResponse:
        """Verify, persist, and activate a connection for subsequent requests.

        Raises:
            ModelConnectionError: Validation, verification, or persistence failed.
        """
        try:
            return factory.configure_model(configuration)
        except (OllamaURLNotAllowedError, httpx.HTTPError) as exc:
            if configuration.provider is ModelProvider.OLLAMA:
                raise _ollama_error(exc) from exc
            raise ModelConnectionError("Model configuration failed.") from exc
        except (ValueError, TypeError, OSError) as exc:
            raise ModelConnectionError("Model configuration failed.") from exc

    def list_ollama_models(self, base_url: str | None) -> list[OllamaModel]:
        """List installed models from an allowed Ollama service.

        Raises:
            OllamaConnectionError: The URL is disallowed or Ollama is unreachable.
        """
        try:
            return factory.list_ollama_models(
                base_url or factory.default_ollama_base_url()
            )
        except (httpx.HTTPError, ValueError) as exc:
            raise _ollama_error(exc) from exc

    def generate_title(self, prompt: str, language: Literal["fa", "en"]) -> str:
        """Generate a sanitized short title with the active model."""
        return factory.generate_conversation_title(prompt, language)

    def suggest_questions(
        self, excerpts: list[str], language: Literal["fa", "en"]
    ) -> list[str]:
        """Generate sanitized document-specific questions with the active model."""
        return factory.suggest_document_questions(excerpts, language)
