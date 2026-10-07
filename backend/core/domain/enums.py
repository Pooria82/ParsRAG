"""Closed vocabularies used across the application boundary."""

from enum import StrEnum
from typing import Literal


class QueryMode(StrEnum):
    """Supported query-routing modes."""

    STRICT = "strict"
    HYBRID = "hybrid"
    LLM_ONLY = "llm-only"


class ModelProvider(StrEnum):
    """Supported runtime model connection types."""

    API = "api"
    OLLAMA = "ollama"


QueryStage = Literal["understanding", "retrieving", "generating", "complete", "failed"]
