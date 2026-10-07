"""Use case: remove every indexed vector that belongs to one session."""

from backend.core.domain.exceptions import InvalidInputError
from backend.core.domain.session import INVALID_SESSION_ID_MESSAGE, is_valid_session_id
from backend.core.dto.output.common import MessageResponse
from backend.core.port.document_repository import DocumentRepository
from backend.core.runtime.session_locks import SessionLocks


class DeleteSession:
    """Delete a session's documents while no ingestion mutates it."""

    def __init__(
        self, repository: DocumentRepository, session_locks: SessionLocks
    ) -> None:
        """Bind the vector-store port and the session mutation locks."""
        self._repository = repository
        self._session_locks = session_locks

    def execute(self, session_id: str) -> MessageResponse:
        """Delete all vectors for the session.

        Raises:
            InvalidInputError: The session ID is malformed.
        """
        if not is_valid_session_id(session_id):
            raise InvalidInputError(INVALID_SESSION_ID_MESSAGE)
        with self._session_locks.hold(session_id):
            self._repository.delete_session(session_id)
        return MessageResponse(message=f"Session '{session_id}' deleted successfully.")
