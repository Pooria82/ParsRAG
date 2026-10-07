"""Use case: name a conversation after its first successful turn."""

from backend.core.dto.input.model import ConversationTitleRequest
from backend.core.dto.output.model import ConversationTitleResponse
from backend.core.port.model_gateway import ModelGateway
from backend.core.runtime.capacity import WorkLimiter


class GenerateConversationTitle:
    """Generate a bounded title using a shared model-work slot."""

    def __init__(self, gateway: ModelGateway, limiter: WorkLimiter) -> None:
        """Bind the model gateway port and the query capacity limiter."""
        self._gateway = gateway
        self._limiter = limiter

    def execute(self, request: ConversationTitleRequest) -> ConversationTitleResponse:
        """Return a short title in the requested interface language.

        Raises:
            CapacityExceededError: Every model-work slot is busy.
        """
        with self._limiter.slot():
            title = self._gateway.generate_title(request.prompt, request.language)
        return ConversationTitleResponse(title=title)
