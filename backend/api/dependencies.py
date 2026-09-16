from collections.abc import Generator

from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import QueryMode
from backend.core.strategies.base_strategy import RAGStrategy
from backend.core.strategies.hybrid_rag import HybridRAGStrategy
from backend.core.strategies.llm_only import LLMOnlyStrategy
from backend.core.strategies.strict_rag import StrictRAGStrategy
from backend.infrastructure.database.qdrant_repo import QdrantRepository


def get_document_repository() -> Generator[AbstractDocumentRepository, None, None]:
    """FastAPI dependency that provides a singleton-like Qdrant repository instance."""
    # In a real heavy-load production scenario, you might share the client
    # via app.state, but QdrantClient inside QdrantRepository handles pooling.
    repo = QdrantRepository()
    try:
        yield repo
    finally:
        pass


def get_query_strategy(
    mode: QueryMode, repo: AbstractDocumentRepository | None = None
) -> RAGStrategy:
    """FastAPI dependency or factory that returns the appropriate RAG strategy.

    Args:
        mode (QueryMode): The execution mode requested by the user.
        repo (AbstractDocumentRepository | None, optional): The injected repository.

    Returns:
        RAGStrategy: The instantiated concrete strategy.
    """
    active_repo = repo if repo is not None else QdrantRepository()
    if mode == QueryMode.STRICT:
        return StrictRAGStrategy(active_repo)
    elif mode == QueryMode.HYBRID:
        return HybridRAGStrategy(active_repo)
    elif mode == QueryMode.LLM_ONLY:
        return LLMOnlyStrategy()
    else:
        # Fallback to Hybrid (though Pydantic validation should prevent this)
        return HybridRAGStrategy(active_repo)
