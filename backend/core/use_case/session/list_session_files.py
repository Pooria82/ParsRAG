"""Use case: enumerate the documents indexed in one session."""

from backend.core.domain.exceptions import InvalidInputError
from backend.core.domain.session import INVALID_SESSION_ID_MESSAGE, is_valid_session_id
from backend.core.port.document_repository import DocumentRepository


class ListSessionFiles:
    """Return the distinct filenames a session can query."""

    def __init__(self, repository: DocumentRepository) -> None:
        """Bind the vector-store port."""
        self._repository = repository

    def execute(self, session_id: str) -> list[str]:
        """List indexed filenames.

        Raises:
            InvalidInputError: The session ID is malformed.
        """
        if not is_valid_session_id(session_id):
            raise InvalidInputError(INVALID_SESSION_ID_MESSAGE)
        return self._repository.get_session_files(session_id)
