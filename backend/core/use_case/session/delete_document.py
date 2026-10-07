"""Use case: remove one indexed document from a session."""

from backend.core.domain.exceptions import InvalidInputError
from backend.core.domain.session import is_valid_session_id
from backend.core.dto.input.documents import DeleteDocumentRequest
from backend.core.dto.output.common import MessageResponse
from backend.core.port.document_repository import DocumentRepository
from backend.core.runtime.session_locks import SessionLocks


class DeleteDocument:
    """Delete one document's chunks without touching the rest of the session."""

    def __init__(
        self, repository: DocumentRepository, session_locks: SessionLocks
    ) -> None:
        """Bind the vector-store port and the session mutation locks."""
        self._repository = repository
        self._session_locks = session_locks

    def execute(
        self, session_id: str, request: DeleteDocumentRequest
    ) -> MessageResponse:
        """Delete the named document.

        Raises:
            InvalidInputError: The session ID is malformed.
        """
        if not is_valid_session_id(session_id):
            raise InvalidInputError("Invalid session_id format.")
        with self._session_locks.hold(session_id):
            self._repository.delete_document(session_id, request.filename)
        return MessageResponse(
            message=f"Document '{request.filename}' deleted successfully."
        )
