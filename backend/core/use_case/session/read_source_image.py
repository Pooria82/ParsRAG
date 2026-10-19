"""Use case: return the preview of an image cited from a session document."""

from backend.core.domain.exceptions import InvalidInputError, NotFoundError
from backend.core.domain.session import INVALID_SESSION_ID_MESSAGE, is_valid_session_id
from backend.core.port.document_repository import DocumentRepository

MAX_FILENAME_LENGTH = 255


class ReadSourceImage:
    """Show the picture an excerpt was read from, next to the excerpt."""

    def __init__(self, repository: DocumentRepository) -> None:
        """Bind the vector-store port."""
        self._repository = repository

    def execute(self, session_id: str, filename: str, number: int) -> bytes:
        """Return the stored preview (WebP).

        Raises:
            InvalidInputError: The session, filename, or image number is invalid.
            NotFoundError: The document has no preview for this image.
        """
        if not is_valid_session_id(session_id):
            raise InvalidInputError(INVALID_SESSION_ID_MESSAGE)
        if not filename or len(filename) > MAX_FILENAME_LENGTH or number < 1:
            raise InvalidInputError("Invalid image reference.")
        image = self._repository.get_image(session_id, filename, number)
        if image is None:
            raise NotFoundError("This image has no stored preview.")
        return image
