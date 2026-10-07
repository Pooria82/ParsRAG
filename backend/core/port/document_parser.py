"""Port for turning uploaded bytes into traceable text sections."""

from typing import Protocol

from backend.core.domain.documents import ParsedDocument


class DocumentParser(Protocol):
    """Extract text sections from one supported document format."""

    def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """Return text sections with location metadata and extraction notices.

        Raises:
            DocumentError: The content is unsupported, malformed, or encrypted.
            EmptyDocumentError: The document has no extractable text.
        """
        ...
