"""Outbound DTOs shared by several operations."""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """A human-readable confirmation of a completed operation."""

    message: str


class StatusResponse(BaseModel):
    """A liveness or readiness state."""

    status: str
