from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class QueryMode(str, Enum):
    STRICT = "strict"
    HYBRID = "hybrid"
    LLM_ONLY = "llm-only"


class ModelProvider(str, Enum):
    """Supported runtime model connection types."""

    API = "api"
    OLLAMA = "ollama"


class ModelConfigurationRequest(BaseModel):
    """Validated runtime model connection settings."""

    provider: ModelProvider
    model_name: str = Field(..., min_length=1, max_length=200)
    base_url: str = Field(..., min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)


class ModelConfigurationResponse(BaseModel):
    """Safe model settings returned to the browser."""

    provider: ModelProvider
    model_name: str
    base_url: str
    api_key_configured: bool


class OllamaModel(BaseModel):
    """One locally installed Ollama model."""

    name: str
    size: int | None = None


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
            max_length=5,
            description="Optional list of filenames to restrict the query to (up to 5)",
        )
    )

    @model_validator(mode="after")
    def require_document_session(self) -> "QueryRequest":
        """Require an isolation boundary for every document-backed query."""
        if self.mode is not QueryMode.LLM_ONLY and self.session_id is None:
            raise ValueError("session_id is required for document-backed queries")
        return self


class DeleteDocumentRequest(BaseModel):
    """Identifies one indexed document to remove from a session."""

    filename: str = Field(..., min_length=1, max_length=255)


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
