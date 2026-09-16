from abc import ABC, abstractmethod

from llama_index.core.llms import ChatMessage

from backend.core.models.domain import QueryResponse


class RAGStrategy(ABC):
    """Abstract base class for all RAG strategies."""

    @abstractmethod
    def execute(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
    ) -> QueryResponse:
        """Executes the specific strategy pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for retrieval depth.

        Returns:
            QueryResponse: The generated answer.
        """
