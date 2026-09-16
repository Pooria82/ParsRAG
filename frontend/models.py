"""Domain and data models for the ParsRAG frontend."""

from typing import Any

from pydantic import BaseModel, Field


class UploadItem(BaseModel):
    """Represents a validated document ready for ingestion.

    Attributes:
        filename: Base name of the file including extension.
        content: Raw binary payload of the document.
    """

    filename: str = Field(..., min_length=1, description="File name with extension")
    content: bytes = Field(..., description="Binary bytes of the file")

    @property
    def size_bytes(self) -> int:
        """Returns the file size in bytes."""
        return len(self.content)


class CitationItem(BaseModel):
    """Represents an individual source citation extracted from search results.

    Attributes:
        index: Sequential 1-based index of the citation.
        filename: Source document filename.
        score: Relevance similarity score from retrieval/reranking.
        text: Text excerpt of the node.
        title: Formatted UI title for the citation element.
        body: Formatted Markdown body of the citation element.
    """

    index: int = Field(..., ge=1, description="1-based citation index")
    filename: str = Field(..., description="Document filename")
    score: float | None = Field(default=None, description="Similarity score")
    text: str = Field(..., description="Extracted content text")
    title: str = Field(..., description="Formatted element title")
    body: str = Field(..., description="Formatted markdown excerpt")


class SessionState(BaseModel):
    """Pydantic model representing the active user chat session state.

    Attributes:
        session_id: Unique alphanumeric identifier for scoped vector indexing.
        mode: Active RAG query mode ('strict', 'hybrid', or 'llm-only').
        top_k: Retrieval depth for Qdrant chunk retrieval.
        chat_history: List of past message dictionaries for conversational memory.
        uploaded_files: List of document filenames ingested into this session.
    """

    session_id: str = Field(..., description="Unique session identifier")
    language: str = Field(
        default="fa", description="Active session language ('fa' or 'en')"
    )
    mode: str = Field(default="hybrid", description="Selected RAG mode")
    strict_rag_threshold: float = Field(
        default=0.80, ge=0.0, le=1.0, description="Strict RAG similarity threshold"
    )
    dynamic_top_k: bool = Field(
        default=True, description="Whether retrieval depth is automated dynamically"
    )
    manual_top_k: int = Field(
        default=15, ge=1, le=50, description="Manual retrieval depth override"
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Effective retrieval depth passed to backend (None = dynamic)",
    )
    max_chat_history_turns: int = Field(
        default=10, ge=2, le=30, description="Conversational history memory limit"
    )
    backend_url: str = Field(
        default="http://localhost:8000", description="FastAPI backend service URL"
    )
    chat_history: list[dict[str, str]] = Field(
        default_factory=list, description="Past conversation turns"
    )
    uploaded_files: list[str] = Field(
        default_factory=list, description="List of filenames active in the session"
    )

    def to_dict(self) -> dict[str, Any]:
        """Serializes session state to a dictionary."""
        return self.model_dump()
