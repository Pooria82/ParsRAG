"""Outbound DTOs for model connections and model-backed helpers."""

from typing import Literal

from pydantic import BaseModel, Field

from backend.core.domain.enums import ModelProvider

ModelConnectionState = Literal[
    "ready", "unreachable", "model_missing", "auth_failed", "key_missing"
]


class ModelConfigurationResponse(BaseModel):
    """Safe model settings returned to the browser."""

    provider: ModelProvider
    model_name: str
    base_url: str
    api_key_configured: bool
    # Hosts the server holds an API key for; a key is only sent to its own host.
    api_key_hosts: list[str] = Field(default_factory=list)
    disclosure_acknowledged: bool = False
    # The server's own Ollama URL, offered when switching from an API to Ollama.
    ollama_base_url: str | None = None


class ModelStatusResponse(BaseModel):
    """Whether the active model service answers right now.

    ``ready``: it answers (and Ollama has the model). ``unreachable``: Ollama is
    not running or the API cannot be reached. ``model_missing``: Ollama runs
    without the selected model. ``auth_failed``: the API rejected the key.
    ``key_missing``: an external API is selected but no key is held for it.
    """

    provider: ModelProvider
    model_name: str
    status: ModelConnectionState


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
