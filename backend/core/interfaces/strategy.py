from abc import ABC, abstractmethod

from backend.core.models.domain import QueryRequest, QueryResponse


class AbstractQueryStrategy(ABC):
    """Abstract interface defining a RAG query strategy."""

    @abstractmethod
    async def execute(self, request: QueryRequest) -> QueryResponse:
        """Executes a full query request through the chosen strategy.

        Args:
            request (QueryRequest): The complete query configuration.

        Returns:
            QueryResponse: The finalized response from the RAG system.
        """
