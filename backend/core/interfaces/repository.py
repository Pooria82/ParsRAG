from abc import ABC, abstractmethod
from typing import List, Optional
from backend.core.models.domain import ExtractedNode

class AbstractDocumentRepository(ABC):
    """Interface for the vector database repository."""

    @abstractmethod
    def save_nodes(self, nodes: List[ExtractedNode], session_id: Optional[str] = None) -> None:
        """Persists extracted nodes to the vector store."""
        pass

    @abstractmethod
    def similarity_search(self, query: str, top_k: int = 5, session_id: Optional[str] = None) -> List[ExtractedNode]:
        """Performs a semantic search for the most relevant nodes."""
        pass

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Deletes all nodes associated with a specific session_id."""
        pass
