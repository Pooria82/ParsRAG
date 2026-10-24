"""Outbound DTOs for update checks and release notes."""

from datetime import datetime

from pydantic import BaseModel, Field


class PublishedRelease(BaseModel):
    """One final release as announced on GitHub."""

    version: str
    url: str
    published_at: datetime | None = None
    body: str = ""


class ReleaseSummary(BaseModel):
    """A release newer than this installation, with its notes in both languages."""

    version: str
    url: str
    published_at: datetime | None = None
    notes_fa: str = ""
    notes_en: str = ""


class UpdateStatusResponse(BaseModel):
    """Whether a newer release exists, and what changed in it.

    ``releases`` lists every newer release, newest first: an update goes
    straight to the latest one, and this is what it brings.
    """

    enabled: bool
    current_version: str
    latest_version: str | None = None
    update_available: bool = False
    checked_at: datetime | None = None
    releases: list[ReleaseSummary] = Field(default_factory=list)


class ReleaseNote(BaseModel):
    """What changed in one installed version."""

    version: str
    notes: str


class ReleaseNotesResponse(BaseModel):
    """Notes of the versions after ``since`` up to the running one, newest first."""

    current_version: str
    notes: list[ReleaseNote] = Field(default_factory=list)
