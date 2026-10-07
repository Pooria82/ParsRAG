"""Outbound DTOs for session document lifecycle operations."""

from pydantic import BaseModel


class ReusedDocumentResponse(BaseModel):
    """The indexed file copied into a session and its chunk count."""

    filename: str
    chunks: int
