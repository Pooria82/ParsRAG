"""Document entities shared by ingestion, retrieval, and answer citations."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class ParsedSection:
    """Text extracted from a traceable document location."""

    text: str
    metadata: dict[str, int]


@dataclass(frozen=True)
class ParsedDocument:
    """All sections of one document plus notices about partial extraction.

    Notices are stable codes such as ``ocr_page_limit`` that tell the user
    part of the document was skipped while the rest is still indexed.
    """

    sections: list[ParsedSection]
    notices: tuple[str, ...] = ()


class ExtractedNode(BaseModel):
    """One document chunk with traceability metadata and optional relevance."""

    text: str = Field(..., description="The chunked text content")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata like page number and source file"
    )
    score: float | None = Field(
        default=None, description="Relevance score from retrieval or reranking"
    )
