"""Strategy port selected per request to answer in Strict, Hybrid, or LLM-only mode."""

from typing import Protocol

from llama_index.core.llms import ChatMessage

from backend.core.dto.output.query import QueryResponse
from backend.core.port.progress_tracker import ProgressCallback


class QueryStrategy(Protocol):
    """One answer-generation pipeline for a single query mode."""

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
        """Executes the specific strategy pipeline.

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
