"""Use case: describe the active model connection."""

from backend.core.dto.output.model import ModelConfigurationResponse
from backend.core.port.model_gateway import ModelGateway


class ReadModelConfiguration:
    """Return the provider, model, and endpoint without exposing credentials."""

    def __init__(self, gateway: ModelGateway) -> None:
        """Bind the model gateway port."""
        self._gateway = gateway

    def execute(self) -> ModelConfigurationResponse:
        """Return the safe view of the active connection."""
        return self._gateway.current_configuration()
