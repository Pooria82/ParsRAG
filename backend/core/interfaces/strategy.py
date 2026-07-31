from abc import ABC, abstractmethod
from backend.core.models.domain import QueryRequest, QueryResponse

class AbstractQueryStrategy(ABC):
    """Interface for RAG Query Strategies (Strict, Hybrid, LLM-Only)."""

    @abstractmethod
    async def execute(self, request: QueryRequest) -> QueryResponse:
        """Executes the specific retrieval and generation logic for the strategy."""
        pass
