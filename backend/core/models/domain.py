from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class QueryMode(str, Enum):
    STRICT = "strict"
    HYBRID = "hybrid"
    LLM_ONLY = "llm-only"


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the sender (e.g., 'user', 'assistant')")
    content: str = Field(..., description="Content of the message")


class QueryRequest(BaseModel):
    prompt: str = Field(..., description="The user's query")
    chat_history: list[ChatMessage] = Field(
        default_factory=list, description="Previous conversation history"
    )
    mode: QueryMode = Field(
        default=QueryMode.HYBRID, description="The RAG execution mode"
    )

    @field_validator("mode", mode="before")
    @classmethod
    def normalize_mode(cls, v: Any) -> Any:
        """Normalizes query mode strings allowing dashes or underscores."""
        if isinstance(v, str):
            return v.strip().lower().replace("_", "-")
        return v

    session_id: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Optional session ID for scoped retrieval (alphanumeric, dashes, underscores only)",
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description="Optional retrieval depth override (1 to 50)",
    )
    file_filter: list[str] | None = Field(
        default=None,
        max_length=5,
        description="Optional list of filenames to restrict the query to (up to 5)",
    )


class DocumentIngestionRequest(BaseModel):
    filename: str = Field(..., description="Name of the file being ingested")
    file_bytes: bytes = Field(..., description="Raw bytes of the file")
    session_id: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Optional session ID to scope the document (alphanumeric, dashes, underscores only)",
    )


class ExtractedNode(BaseModel):
    text: str = Field(..., description="The chunked text content")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata like page number and source file"
    )
    score: float | None = Field(
        default=None, description="Relevance score from retrieval or reranking"
    )


class QueryResponse(BaseModel):
    answer: str = Field(..., description="The generated response from the LLM")
    source_nodes: list[ExtractedNode] = Field(
        default_factory=list, description="Citations and source chunks used"
    )
