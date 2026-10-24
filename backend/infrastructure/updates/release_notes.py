"""``ReleaseNotes`` over the ``release-notes`` folder shipped with the app."""

import re
from pathlib import Path
from typing import Literal

from backend.infrastructure.version import PROJECT_ROOT

_NOTE = re.compile(r"^(\d+\.\d+\.\d+)\.(fa|en)\.md$")


class LocalReleaseNotes:
    """Read ``<version>.<language>.md`` files written for each release."""

    def __init__(self, directory: Path = PROJECT_ROOT / "release-notes") -> None:
        """Use the project's ``release-notes`` folder by default."""
        self._directory = directory

    def versions(self) -> list[str]:
        """Return every version with at least one notes file."""
        if not self._directory.is_dir():
            return []
        found = {
            match.group(1)
            for path in self._directory.iterdir()
            if (match := _NOTE.match(path.name))
        }
        return sorted(found)

    def notes(self, version: str, language: Literal["fa", "en"]) -> str | None:
        """Return the notes of ``version`` in ``language``, if the file exists."""
        path = self._directory / f"{version}.{language}.md"
        if not _NOTE.match(path.name) or not path.is_file():
            return None
        return path.read_text(encoding="utf-8").strip() or None
