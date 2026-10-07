"""Use case: copy an indexed document between local conversations."""

from collections.abc import Callable

from backend.core.domain.exceptions import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
)
from backend.core.domain.session import is_valid_session_id
from backend.core.domain.upload_policy import UploadPolicy
from backend.core.dto.input.documents import ReuseDocumentRequest
from backend.core.dto.output.documents import ReusedDocumentResponse
from backend.core.port.document_repository import DocumentRepository
from backend.core.runtime.capacity import WorkLimiter
from backend.core.runtime.session_locks import SessionLocks


class ReuseDocument:
    """Reuse existing vectors instead of re-uploading, re-parsing, and re-embedding."""

    def __init__(
        self,
        repository: DocumentRepository,
        limiter: WorkLimiter,
        session_locks: SessionLocks,
        policy_provider: Callable[[], UploadPolicy] = UploadPolicy.from_environment,
    ) -> None:
        """Bind the vector-store port and the ingestion runtime controls."""
        self._repository = repository
        self._limiter = limiter
        self._session_locks = session_locks
        self._policy_provider = policy_provider

    def execute(
        self, session_id: str, request: ReuseDocumentRequest
    ) -> ReusedDocumentResponse:
        """Copy one document's vectors into the target session.

        Raises:
            InvalidInputError: The target is malformed, equals the source, or is full.
            NotFoundError: The source document does not exist.
            ConflictError: The target already contains the filename.
            CapacityExceededError: Every ingestion slot is busy.
        """
        if (
            not is_valid_session_id(session_id)
            or session_id == request.source_session_id
        ):
            raise InvalidInputError("Invalid target session.")
        with (
            self._limiter.slot(),
            self._session_locks.hold(session_id, request.source_session_id),
        ):
            source_files = self._repository.get_session_files(request.source_session_id)
            if request.filename not in source_files:
                raise NotFoundError("Source document was not found.")
            target_files = self._repository.get_session_files(session_id)
            if request.filename in target_files:
                raise ConflictError(
                    "The target session already contains this filename."
                )
            if len(target_files) >= self._policy_provider().max_files_per_session:
                raise InvalidInputError("The target session is full.")
            copied = self._repository.copy_document(
                request.source_session_id, session_id, request.filename
            )
            if not copied:
                raise NotFoundError("Source document was not found.")
        return ReusedDocumentResponse(filename=request.filename, chunks=copied)
