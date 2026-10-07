"""Document entities shared by ingestion, retrieval, and answer citations."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ParsedSection:
    """Text extracted from a traceable document location."""

    text: str
    metadata: dict[str, int]


class ExtractedNode(BaseModel):
    """One document chunk with traceability metadata and optional relevance."""

    text: str = Field(..., description="The chunked text content")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata like page number and source file"
    )
    score: float | None = Field(
        default=None, description="Relevance score from retrieval or reranking"
    )
