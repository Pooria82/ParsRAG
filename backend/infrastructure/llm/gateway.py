"""``ModelGateway`` adapter over the LlamaIndex model factory."""

from typing import Literal

import httpx

from backend.core.domain.exceptions import ModelConnectionError
from backend.core.dto.input.model import ModelConfigurationRequest
from backend.core.dto.output.model import ModelConfigurationResponse, OllamaModel
from backend.infrastructure.llm import factory


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
        except (ValueError, TypeError, OSError, httpx.HTTPError) as exc:
            raise ModelConnectionError("Model configuration failed.") from exc

    def list_ollama_models(self, base_url: str) -> list[OllamaModel]:
        """List installed models from a loopback or internal Ollama service.

        Raises:
            ModelConnectionError: The URL is disallowed or Ollama is unreachable.
        """
        try:
            return factory.list_ollama_models(base_url)
        except (httpx.HTTPError, ValueError) as exc:
            raise ModelConnectionError("Ollama is unavailable.") from exc

    def generate_title(self, prompt: str, language: Literal["fa", "en"]) -> str:
        """Generate a sanitized short title with the active model."""
        return factory.generate_conversation_title(prompt, language)

    def suggest_questions(
        self, excerpts: list[str], language: Literal["fa", "en"]
    ) -> list[str]:
        """Generate sanitized document-specific questions with the active model."""
        return factory.suggest_document_questions(excerpts, language)
