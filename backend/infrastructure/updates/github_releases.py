"""``ReleaseFeed`` over the public GitHub releases of the project.

Only anonymous GET requests to fixed GitHub addresses are made, with nothing
about the installation in them; GitHub sees the address the request comes from.
"""

import os
from datetime import datetime
from typing import Any, Literal

import httpx

from backend.core.domain.versioning import parse_version
from backend.core.dto.output.updates import PublishedRelease

DEFAULT_REPOSITORY = "Pooria82/ParsRAG"
_TIMEOUT_SECONDS = 6.0


def update_repository() -> str:
    """``owner/name`` of the repository whose releases are checked."""
    return (
        os.getenv("PARSRAG_UPDATE_REPOSITORY", DEFAULT_REPOSITORY).strip()
        or DEFAULT_REPOSITORY
    )


class GitHubReleaseFeed:
    """Read releases from the GitHub API and notes from the tagged sources."""

    def __init__(self, current_version: str, repository: str | None = None) -> None:
        """Identify requests with the running version, as GitHub asks."""
        self._repository = repository or update_repository()
        self._headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": f"ParsRAG/{current_version}",
        }

    def releases(self) -> list[PublishedRelease]:
        """Return final releases, newest first.

        Raises:
            httpx.HTTPError: GitHub could not be reached or refused the request.
        """
        response = httpx.get(
            f"https://api.github.com/repos/{self._repository}/releases",
            params={"per_page": 30},
            headers=self._headers,
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        items = payload if isinstance(payload, list) else []
        return [release for item in items if (release := _release(item)) is not None]

    def notes(self, version: str, language: Literal["fa", "en"]) -> str | None:
        """Return ``release-notes/<version>.<language>.md`` at the release tag."""
        response = httpx.get(
            f"https://raw.githubusercontent.com/{self._repository}/v{version}"
            f"/release-notes/{version}.{language}.md",
            headers=self._headers,
            timeout=_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return None
        return response.text.strip() or None


def _release(item: Any) -> PublishedRelease | None:
    if not isinstance(item, dict) or item.get("draft") or item.get("prerelease"):
        return None
    tag = item.get("tag_name")
    if not isinstance(tag, str) or parse_version(tag) is None:
        return None
    published = item.get("published_at")
    return PublishedRelease(
        version=tag.removeprefix("v"),
        url=str(item.get("html_url") or ""),
        published_at=datetime.fromisoformat(published)
        if isinstance(published, str)
        else None,
        body=str(item.get("body") or "").strip(),
    )
