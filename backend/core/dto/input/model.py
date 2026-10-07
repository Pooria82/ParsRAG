"""Inbound DTOs for model connections and model-backed helpers."""

from typing import Literal

from pydantic import BaseModel, Field

from backend.core.domain.enums import ModelProvider


class ModelConfigurationRequest(BaseModel):
    """Validated runtime model connection settings."""

    provider: ModelProvider
    model_name: str = Field(..., min_length=1, max_length=200)
    base_url: str = Field(..., min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=1000)
    disclosure_acknowledged: bool = False


class QuestionSuggestionRequest(BaseModel):
    """Interface language and, optionally, the documents to draw on."""

    language: Literal["fa", "en"] = "fa"
    files: list[str] | None = Field(default=None, max_length=50)


class ConversationTitleRequest(BaseModel):
    """Validated input for generating a short conversation title."""

    prompt: str = Field(..., min_length=1, max_length=12_000)
    language: Literal["fa", "en"] = "fa"
