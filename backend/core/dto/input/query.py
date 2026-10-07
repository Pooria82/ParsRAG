"""Inbound DTOs for question answering."""

from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.core.domain.enums import QueryMode


class ChatMessage(BaseModel):
    """One bounded conversational history item."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=12_000)


class QueryRequest(BaseModel):
    """Validated query and its session-scoped context."""

    prompt: str = Field(..., min_length=1, max_length=12_000)
    chat_history: list[ChatMessage] = Field(
        default_factory=list, max_length=20, description="Previous conversation history"
    )
    mode: QueryMode = Field(
        default=QueryMode.HYBRID, description="The RAG execution mode"
    )
    request_id: UUID | None = Field(
        default=None,
        description="Optional opaque identifier used to read non-sensitive progress state",
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
    file_filter: list[Annotated[str, Field(min_length=1, max_length=255)]] | None = (
        Field(
            default=None,
            max_length=50,
            description="Optional list of filenames to restrict the query to",
        )
    )

    @model_validator(mode="after")
    def require_document_session(self) -> "QueryRequest":
        """Require an isolation boundary for every document-backed query."""
        if self.mode is not QueryMode.LLM_ONLY and self.session_id is None:
            raise ValueError("session_id is required for document-backed queries")
        return self
