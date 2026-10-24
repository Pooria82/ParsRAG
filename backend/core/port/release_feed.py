"""Ports for published releases and the notes shipped with each version."""

from typing import Literal, Protocol

from backend.core.dto.output.updates import PublishedRelease


class ReleaseFeed(Protocol):
    """Published releases of ParsRAG, read from where they are announced."""

    def releases(self) -> list[PublishedRelease]:
        """Return final releases, newest first (no drafts or pre-releases)."""
        ...

    def notes(self, version: str, language: Literal["fa", "en"]) -> str | None:
        """Return the release notes of ``version`` in ``language``, if published."""
        ...


class ReleaseNotes(Protocol):
    """Release notes of the versions that came with this installation."""

    def versions(self) -> list[str]:
        """Return every version that has notes here."""
        ...

    def notes(self, version: str, language: Literal["fa", "en"]) -> str | None:
        """Return the notes of ``version`` in ``language``, if any."""
        ...
