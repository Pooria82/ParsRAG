import os
from collections.abc import Generator
from functools import lru_cache

from backend.core.port.document_repository import DocumentRepository
from backend.core.domain.enums import QueryMode
from backend.core.port.query_strategy import QueryStrategy
from backend.core.strategies.hybrid_rag import HybridRAGStrategy
from backend.core.strategies.llm_only import LLMOnlyStrategy
from backend.core.strategies.strict_rag import StrictRAGStrategy
from backend.infrastructure.database.qdrant_repo import QdrantRepository


@lru_cache(maxsize=1)
def _shared_document_repository() -> DocumentRepository:
    """Create the process-wide repository and reuse its pooled client."""
    host = os.getenv("QDRANT_HOST", "localhost")
    try:
        port = int(os.getenv("QDRANT_PORT", "6333"))
    except ValueError:
        port = 6333
    return QdrantRepository(host=host, port=port)


def get_document_repository() -> Generator[DocumentRepository, None, None]:
    """Provide the shared document repository to FastAPI routes."""
    yield _shared_document_repository()


def get_query_strategy(
    mode: QueryMode, repo: DocumentRepository | None = None
) -> QueryStrategy:
    """FastAPI dependency or factory that returns the appropriate RAG strategy.

    Args:
        mode (QueryMode): The execution mode requested by the user.
        repo (DocumentRepository | None, optional): The injected repository.

    Returns:
        QueryStrategy: The instantiated concrete strategy.
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
