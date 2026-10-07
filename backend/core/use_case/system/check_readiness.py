"""Use case: report whether model and storage adapters can accept work."""

from collections.abc import Callable

from backend.core.port.document_repository import DocumentRepository
from backend.core.runtime.readiness import RuntimeState


class CheckReadiness:
    """Combine initialization state with a live vector-store probe."""

    def __init__(
        self,
        runtime: RuntimeState,
        repository_provider: Callable[[], DocumentRepository],
    ) -> None:
        """Bind runtime state and a lazy repository provider.

        The repository is resolved only once initialization reports ready, so a
        readiness probe never opens a store connection while models are loading.
        """
        self._runtime = runtime
        self._repository_provider = repository_provider

    def execute(self) -> str:
        """Return ``ready``, ``preparing``, or ``failed``."""
        status = self._runtime.status()
        if status != "ready":
            return status
        return "ready" if self._repository_provider().is_ready() else "failed"
