"""Port for reordering retrieved chunks by query relevance."""

from typing import Protocol

from backend.core.domain.documents import ExtractedNode


class Reranker(Protocol):
    """Score candidate chunks against a question with a cross-encoder."""

    def rerank(
        self, query: str, nodes: list[ExtractedNode], top_n: int
    ) -> list[ExtractedNode]:
        """Return at most ``top_n`` nodes, most relevant first, with new scores."""
        ...
