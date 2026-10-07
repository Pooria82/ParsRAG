"""Outbound DTOs for document ingestion."""

from pydantic import BaseModel, Field

from backend.core.dto.output.common import MessageResponse


class IngestedFile(BaseModel):
    """What was indexed for one uploaded file."""

    filename: str
    chunks: int
    sections: int = Field(description="Pages, slides, paragraphs, or blocks read")
    notices: list[str] = Field(
        default_factory=list,
        description="Codes for skipped parts, e.g. ocr_page_limit or ocr_partial",
    )


class IngestResponse(MessageResponse):
    """Summary message plus per-file indexing details."""

    files: list[IngestedFile] = Field(default_factory=list)
