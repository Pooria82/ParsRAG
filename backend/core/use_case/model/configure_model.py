"""Use case: verify and activate a new model connection."""

from backend.core.domain.exceptions import InvalidInputError, ModelConnectionError
from backend.core.dto.input.model import ModelConfigurationRequest
from backend.core.dto.output.model import ModelConfigurationResponse
from backend.core.port.model_gateway import ModelGateway


class ConfigureModel:
    """Switch subsequent queries to a verified local, private, or external model."""

    def __init__(self, gateway: ModelGateway) -> None:
        """Bind the model gateway port."""
        self._gateway = gateway

    def execute(
        self, configuration: ModelConfigurationRequest
    ) -> ModelConfigurationResponse:
        """Apply the connection or report a single non-revealing failure.

        Raises:
            InvalidInputError: The connection could not be verified or saved.
        """
        try:
            return self._gateway.configure(configuration)
        except ModelConnectionError as exc:
            raise InvalidInputError(
                "The model connection could not be verified or saved."
            ) from exc
