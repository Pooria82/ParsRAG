from abc import ABC, abstractmethod

from backend.core.models.domain import ExtractedNode


class AbstractDocumentRepository(ABC):
    """Abstract interface defining the Document Repository contract."""

    @abstractmethod
    def save_nodes(
        self, nodes: list[ExtractedNode], session_id: str | None = None
    ) -> None:
        """Saves extracted document nodes into the repository.

        Args:
            nodes (list[ExtractedNode]): The nodes to save.
            session_id (str | None, optional): The session ID associated with these nodes.
        """

    @abstractmethod
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

    @abstractmethod
    def get_session_files(self, session_id: str) -> list[str]:
        """Returns the list of distinct filenames indexed in the given session.

        Args:
            session_id (str): The session ID to inspect.

        Returns:
            list[str]: Distinct filenames in the session.
        """

    @abstractmethod
    def delete_session(self, session_id: str) -> None:
        """Deletes all nodes belonging to the given session.

        Args:
            session_id (str): The session ID to delete.
        """
