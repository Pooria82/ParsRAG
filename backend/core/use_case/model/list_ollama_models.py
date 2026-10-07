"""Use case: list the models installed on a local Ollama service."""

from backend.core.domain.exceptions import ModelConnectionError, UpstreamServiceError
from backend.core.dto.output.model import OllamaModel
from backend.core.port.model_gateway import ModelGateway


class ListOllamaModels:
    """Offer locally installed models for selection."""

    def __init__(self, gateway: ModelGateway) -> None:
        """Bind the model gateway port."""
        self._gateway = gateway

    def execute(self, base_url: str) -> list[OllamaModel]:
        """List models from a loopback or internal Ollama endpoint.

        Raises:
            UpstreamServiceError: Ollama is unreachable or the URL is disallowed.
        """
        try:
            return self._gateway.list_ollama_models(base_url)
        except ModelConnectionError as exc:
            raise UpstreamServiceError("Could not connect to Ollama.") from exc
