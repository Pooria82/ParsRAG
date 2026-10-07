"""In-memory port fakes for framework-free use-case tests."""

from typing import Any

from backend.core.domain.documents import ExtractedNode, ParsedSection


class InMemoryRepository:
    """``DocumentRepository`` fake that stores chunks per session in memory."""

    def __init__(self) -> None:
        """Start with no sessions."""
        self.sessions: dict[str, list[ExtractedNode]] = {}

    def is_ready(self) -> bool:
        """Always reachable."""
        return True

    def save_nodes(self, nodes: list[ExtractedNode], session_id: str) -> None:
        """Append chunks to a session."""
        self.sessions.setdefault(session_id, []).extend(nodes)

    def similarity_search(
        self,
        query: str,
        top_k: int = 15,
        session_id: str | None = None,
        file_filter: list[str] | None = None,
    ) -> list[ExtractedNode]:
        """Return the first stored chunks of a session."""
        return self.sessions.get(session_id or "", [])[:top_k]

    def get_session_files(self, session_id: str) -> list[str]:
        """Return distinct filenames in insertion order."""
        names: list[str] = []
        for node in self.sessions.get(session_id, []):
            if node.metadata["filename"] not in names:
                names.append(node.metadata["filename"])
        return names

    def delete_session(self, session_id: str) -> None:
        """Drop a session."""
        self.sessions.pop(session_id, None)

    def delete_document(self, session_id: str, filename: str) -> None:
        """Drop one document's chunks."""
        self.sessions[session_id] = [
            node
            for node in self.sessions.get(session_id, [])
            if node.metadata["filename"] != filename
        ]

    def copy_document(
        self, source_session_id: str, target_session_id: str, filename: str
    ) -> int:
        """Copy one document's chunks between sessions."""
        copied = [
            node
            for node in self.sessions.get(source_session_id, [])
            if node.metadata["filename"] == filename
        ]
        self.save_nodes(copied, target_session_id)
        return len(copied)


class FakeParser:
    """``DocumentParser`` fake returning preset sections."""

    def __init__(self, sections: list[ParsedSection] | None = None) -> None:
        """Use one page of text unless sections are given."""
        self.sections = sections or [ParsedSection("text", {"page": 1})]

    def parse_sections(self, file_bytes: bytes, filename: str) -> list[ParsedSection]:
        """Return the preset sections."""
        return self.sections


class FakeChunker:
    """``TextChunker`` fake producing one chunk per section."""

    def chunk(self, text: str, metadata: dict[str, Any]) -> list[ExtractedNode]:
        """Wrap the whole section in one chunk."""
        return [ExtractedNode(text=text, metadata=metadata)]

    def bridge(
        self,
        previous_text: str,
        current_text: str,
        *,
        filename: str,
        previous_page: int,
        current_page: int,
    ) -> ExtractedNode | None:
        """Bridge only consecutive pages."""
        if current_page != previous_page + 1:
            return None
        return ExtractedNode(
            text=f"{previous_text} {current_text}",
            metadata={"filename": filename, "page": previous_page},
        )
