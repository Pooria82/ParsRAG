"""Vector-store port isolating the core from Qdrant and its client library."""

from typing import Protocol

from backend.core.domain.documents import ExtractedNode


class DocumentRepository(Protocol):
    """Session-scoped storage and similarity search for document chunks."""

    def is_ready(self) -> bool:
        """Return whether the backing store and active collection are reachable."""
        ...

    def save_nodes(self, nodes: list[ExtractedNode], session_id: str) -> None:
        """Saves extracted document nodes into the repository.

        Args:
            nodes (list[ExtractedNode]): The nodes to save.
            session_id: The required session isolation boundary.
        """
        ...

    def similarity_search(
        self,
        query: str,
        top_k: int = 15,
        session_id: str | None = None,
        file_filter: list[str] | None = None,
    ) -> list[ExtractedNode]:
        """Performs a similarity search to find nodes matching the query.

        Args:
            query (str): The search query.
            top_k (int, optional): The number of closest matches. Defaults to 15.
            session_id (str | None, optional): Session ID for filtering.
            file_filter (list[str] | None, optional): Optional list of filenames to filter by.

        Returns:
            list[ExtractedNode]: The top matching nodes.
        """
        ...

    def get_session_files(self, session_id: str) -> list[str]:
        """Returns the list of distinct filenames indexed in the given session.

        Args:
            session_id (str): The session ID to inspect.

        Returns:
            list[str]: Distinct filenames in the session.
        """
        ...

    def delete_session(self, session_id: str) -> None:
        """Deletes all nodes belonging to the given session.

        Args:
            session_id (str): The session ID to delete.
        """
        ...

    def delete_document(self, session_id: str, filename: str) -> None:
        """Deletes every chunk for one document in a session."""
        ...

    def copy_document(
        self, source_session_id: str, target_session_id: str, filename: str
    ) -> int:
        """Copy existing vectors in bounded pages; return the copied chunk count."""
        ...
