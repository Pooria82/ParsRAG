from abc import ABC, abstractmethod

from llama_index.core.llms import ChatMessage

from backend.core.models.domain import QueryResponse
from backend.core.query_progress import ProgressCallback


class RAGStrategy(ABC):
    """Abstract base class for all RAG strategies."""

    @abstractmethod
    def execute(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
        file_filter: list[str] | None = None,
        progress: ProgressCallback | None = None,
    ) -> QueryResponse:
        """Executes the specific strategy pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for retrieval depth.
            file_filter (list[str] | None, optional): Optional list of filenames to restrict to.
            progress (ProgressCallback | None, optional): Reports coarse pipeline stages.

        Returns:
            QueryResponse: The generated answer.
        """
