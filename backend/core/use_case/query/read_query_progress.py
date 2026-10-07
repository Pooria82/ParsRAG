"""Use case: report the coarse stage of an in-flight query."""

from uuid import UUID

from backend.core.domain.exceptions import NotFoundError
from backend.core.dto.output.query import QueryProgressResponse
from backend.core.port.progress_tracker import ProgressTracker


class ReadQueryProgress:
    """Expose pipeline stages without prompts, answers, or document data."""

    def __init__(self, progress: ProgressTracker) -> None:
        """Bind the progress port."""
        self._progress = progress

    def execute(self, request_id: UUID) -> QueryProgressResponse:
        """Return the latest stage for an opaque request ID.

        Raises:
            NotFoundError: No unexpired stage exists for the ID.
        """
        stage = self._progress.get_stage(str(request_id))
        if stage is None:
            raise NotFoundError("Query progress was not found.")
        return QueryProgressResponse(stage=stage)
