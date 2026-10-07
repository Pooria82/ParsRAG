"""Port for splitting parsed sections into retrievable chunks."""

from typing import Any, Protocol

from backend.core.domain.documents import ExtractedNode


class TextChunker(Protocol):
    """Split text into embedding-sized chunks and bridge page boundaries."""

    def chunk(self, text: str, metadata: dict[str, Any]) -> list[ExtractedNode]:
        """Split one section into chunks that all carry its metadata."""
        ...

    def bridge(
        self,
        previous_text: str,
        current_text: str,
        *,
        filename: str,
        previous_page: int,
        current_page: int,
    ) -> ExtractedNode | None:
        """Return a chunk spanning two adjacent pages, or None if not adjacent."""
        ...
