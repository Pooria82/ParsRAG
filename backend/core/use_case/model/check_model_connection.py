"""Use case: report whether the active model service answers."""

from backend.core.dto.output.model import ModelStatusResponse
from backend.core.port.model_gateway import ModelGateway


class CheckModelConnection:
    """Tell the browser whether questions can reach the model right now."""

    def __init__(self, gateway: ModelGateway) -> None:
        """Bind the model gateway port."""
        self._gateway = gateway

    def execute(self) -> ModelStatusResponse:
        """Return ``ready``, ``unreachable``, ``model_missing``, or ``auth_failed``."""
        return self._gateway.connection_status()
