"""Outbound DTOs for model connections and model-backed helpers."""

from pydantic import BaseModel, Field

from backend.core.domain.enums import ModelProvider


class ModelConfigurationResponse(BaseModel):
    """Safe model settings returned to the browser."""

    provider: ModelProvider
    model_name: str
    base_url: str
    api_key_configured: bool
    disclosure_acknowledged: bool = False
    # The server's own Ollama URL, offered when switching from an API to Ollama.
    ollama_base_url: str | None = None


class QuestionSuggestionResponse(BaseModel):
    """Short questions the session's documents can answer."""

    questions: list[str] = Field(default_factory=list, max_length=3)


class ConversationTitleResponse(BaseModel):
    """A bounded title suitable for conversation navigation."""

    title: str = Field(..., min_length=1, max_length=80)


class OllamaModel(BaseModel):
    """One locally installed Ollama model."""

    name: str
    size: int | None = None
