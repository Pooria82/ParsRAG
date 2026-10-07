"""Port for turning uploaded bytes into traceable text sections."""

from typing import Protocol

from backend.core.domain.documents import ParsedSection


class DocumentParser(Protocol):
    """Extract text sections from one supported document format."""

    def parse_sections(self, file_bytes: bytes, filename: str) -> list[ParsedSection]:
        """Return text sections with location metadata such as page numbers.

        Raises:
            ValueError: The content is unsupported, malformed, or exceeds OCR limits.
            EmptyDocumentError: The document has no extractable text.
        """
        ...
