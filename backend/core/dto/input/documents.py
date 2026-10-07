"""Inbound DTOs for session document lifecycle operations."""

from pydantic import BaseModel, Field


class DeleteDocumentRequest(BaseModel):
    """Identifies one indexed document to remove from a session."""

    filename: str = Field(..., min_length=1, max_length=255)


class ReuseDocumentRequest(BaseModel):
    """Copy an indexed file from another local conversation without re-uploading."""

    source_session_id: str = Field(
        ..., min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    filename: str = Field(..., min_length=1, max_length=255)
