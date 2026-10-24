"""Use case: show what changed after an update."""

from typing import Literal

from backend.core.domain.versioning import is_newer, parse_version
from backend.core.dto.output.updates import ReleaseNote, ReleaseNotesResponse
from backend.core.port.release_feed import ReleaseNotes


class ReadReleaseNotes:
    """Collect the notes of every version installed since the user last looked.

    Skipped versions are included: an update goes straight to the latest
    release, and the user still sees everything it brought.
    """

    def __init__(self, notes: ReleaseNotes, current_version: str) -> None:
        """Bind the shipped notes and the running version."""
        self._notes = notes
        self._current = current_version

    def execute(
        self, since: str | None, language: Literal["fa", "en"]
    ) -> ReleaseNotesResponse:
        """Notes after ``since`` up to the running version, newest first.

        Without ``since`` only the running version's notes are returned.
        """
        versions = [
            version
            for version in self._notes.versions()
            if not is_newer(version, self._current)
            and (
                is_newer(version, since)
                if since and parse_version(since)
                else version == self._current
            )
        ]
        versions.sort(
            key=lambda version: parse_version(version) or (0, 0, 0), reverse=True
        )
        notes = []
        for version in versions:
            text = self._notes.notes(version, language) or self._notes.notes(
                version, "en"
            )
            if text:
                notes.append(ReleaseNote(version=version, notes=text))
        return ReleaseNotesResponse(current_version=self._current, notes=notes)
