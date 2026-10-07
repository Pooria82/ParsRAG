"""Port for configuring and using the active generation model."""

from typing import Literal, Protocol

from backend.core.dto.input.model import ModelConfigurationRequest
from backend.core.dto.output.model import ModelConfigurationResponse, OllamaModel


class ModelGateway(Protocol):
    """Manage the runtime model connection without exposing secrets.

    Implementations raise ``ModelConnectionError`` for every verification,
    transport, or persistence failure so the core never sees client libraries.
    """

    def current_configuration(self) -> ModelConfigurationResponse:
        """Return the active connection without its API key."""
        ...

    def configure(
        self, configuration: ModelConfigurationRequest
    ) -> ModelConfigurationResponse:
        """Verify, persist, and activate a model connection."""
        ...

    def list_ollama_models(self, base_url: str) -> list[OllamaModel]:
        """List models installed on a local Ollama service."""
        ...

    def generate_title(self, prompt: str, language: Literal["fa", "en"]) -> str:
        """Generate a short conversation title with the active model."""
        ...
