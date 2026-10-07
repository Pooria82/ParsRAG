"""Strategy port selected per request to answer in Strict, Hybrid, or LLM-only mode."""

from collections.abc import Iterator
from typing import Protocol

from llama_index.core.llms import ChatMessage

from backend.core.dto.output.query import PreparedAnswer, QueryResponse
from backend.core.port.progress_tracker import ProgressCallback


class QueryStrategy(Protocol):
    """One answer-generation pipeline for a single query mode."""

    def prepare(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
        file_filter: list[str] | None = None,
        progress: ProgressCallback | None = None,
        document_segments: list[tuple[str, str]] | None = None,
    ) -> PreparedAnswer:
        """Retrieve evidence and build the prompt, or decide not to generate."""
        ...

    def execute(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
        file_filter: list[str] | None = None,
        progress: ProgressCallback | None = None,
        document_segments: list[tuple[str, str]] | None = None,
    ) -> QueryResponse:
        """Prepare and generate the whole answer.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for retrieval depth.
            file_filter (list[str] | None, optional): Optional list of filenames to restrict to.
            progress (ProgressCallback | None, optional): Reports coarse pipeline stages.
            document_segments: Explicit file-scoped question segments.

        Returns:
            QueryResponse: The generated answer.
        """
        ...

    def stream(self, prepared: PreparedAnswer) -> Iterator[str]:
        """Yield the answer to a prepared prompt as text deltas."""
        ...
