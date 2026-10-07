"""Port for publishing coarse, non-sensitive query pipeline stages."""

from collections.abc import Callable
from typing import Protocol

from backend.core.domain.enums import QueryStage

ProgressCallback = Callable[[QueryStage], None]


class ProgressTracker(Protocol):
    """Short-lived stage storage keyed by an opaque client request ID."""

    def set_stage(self, request_id: str, stage: QueryStage) -> None:
        """Record the latest stage for one request."""
        ...

    def get_stage(self, request_id: str) -> QueryStage | None:
        """Return the latest unexpired stage, if any."""
        ...
