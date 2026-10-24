"""Update checks: once a day, silent offline, and every newer release listed."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_check_for_updates, get_read_release_notes
from backend.core.domain.versioning import is_newer, parse_version
from backend.core.dto.output.updates import PublishedRelease
from backend.core.use_case.system.check_for_updates import (
    CHECK_INTERVAL_SECONDS,
    MANUAL_CHECK_SECONDS,
    CheckForUpdates,
)
from backend.core.use_case.system.read_release_notes import ReadReleaseNotes
from backend.infrastructure.updates.github_releases import GitHubReleaseFeed
from backend.infrastructure.updates.release_notes import LocalReleaseNotes
from backend.main import app


class Feed:
    """Release feed fake that counts requests and can be offline."""

    def __init__(self, versions: list[str], offline: bool = False) -> None:
        """Publish ``versions``."""
        self.versions = versions
        self.offline = offline
        self.calls = 0

    def releases(self) -> list[PublishedRelease]:
        """Return the releases, or fail like a missing network."""
        self.calls += 1
        if self.offline:
            raise httpx.ConnectError("offline")
        return [
            PublishedRelease(
                version=v, url=f"https://example.test/v{v}", body=f"body {v}"
            )
            for v in self.versions
        ]

    def notes(self, version: str, language: Literal["fa", "en"]) -> str | None:
        """Persian notes exist only for 1.3.0."""
        return f"یادداشت {version}" if language == "fa" and version == "1.3.0" else None


class Clock:
    """Monotonic clock that tests move by hand."""

    def __init__(self) -> None:
        """Start at zero."""
        self.now = 0.0

    def __call__(self) -> float:
        """Return the current time."""
        return self.now


def test_versions_compare_numerically() -> None:
    assert parse_version("v1.10.0") == (1, 10, 0)
    assert parse_version("1.2.0-rc1") is None
    assert is_newer("1.10.0", "1.9.9")
    assert not is_newer("1.1.1", "1.1.1")
    assert not is_newer("2.0.0-beta", "1.0.0")


def test_every_newer_release_is_listed_newest_first_with_notes() -> None:
    feed = Feed(["1.1.0", "1.3.0", "1.2.0", "1.1.1"])
    status = CheckForUpdates(feed, "1.1.1", lambda: True, Clock()).execute()

    assert status.update_available and status.latest_version == "1.3.0"
    assert [r.version for r in status.releases] == ["1.3.0", "1.2.0"]
    assert status.releases[0].notes_fa == "یادداشت 1.3.0"
    # Without a Persian file the GitHub text is shown.
    assert status.releases[1].notes_fa == "body 1.2.0"


def test_github_is_asked_once_a_day_and_check_now_at_most_every_minute() -> None:
    feed, clock = Feed(["1.2.0"]), Clock()
    checker = CheckForUpdates(feed, "1.1.1", lambda: True, clock)
    checker.execute()
    clock.now += 30
    checker.execute(refresh=True)
    assert feed.calls == 1
    clock.now += MANUAL_CHECK_SECONDS
    checker.execute(refresh=True)
    assert feed.calls == 2
    clock.now += CHECK_INTERVAL_SECONDS
    checker.execute()
    assert feed.calls == 3


def test_offline_keeps_the_last_result_and_never_fails() -> None:
    feed, clock = Feed(["1.2.0"]), Clock()
    checker = CheckForUpdates(feed, "1.1.1", lambda: True, clock)
    assert checker.execute().update_available
    feed.offline = True
    clock.now += CHECK_INTERVAL_SECONDS
    assert checker.execute().latest_version == "1.2.0"

    fresh = CheckForUpdates(Feed([], offline=True), "1.1.1", lambda: True, Clock())
    status = fresh.execute()
    assert status.enabled and not status.update_available and status.checked_at is None


def test_a_disabled_check_asks_nothing() -> None:
    feed = Feed(["9.0.0"])
    status = CheckForUpdates(feed, "1.1.1", lambda: False, Clock()).execute()
    assert not status.enabled and not status.update_available
    assert feed.calls == 0


def _notes(tmp_path: Path) -> LocalReleaseNotes:
    for name, text in {
        "1.1.2.fa.md": "تازه‌های ۱٫۱٫۲",
        "1.1.2.en.md": "New in 1.1.2",
        "1.2.0.en.md": "New in 1.2.0",
        "1.3.0.fa.md": "future",
        "notes.md": "ignored",
    }.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return LocalReleaseNotes(tmp_path)


def test_notes_cover_every_version_since_the_last_one_seen(tmp_path: Path) -> None:
    reader = ReadReleaseNotes(_notes(tmp_path), "1.2.0")

    skipped = reader.execute("1.1.1", "fa")
    assert [(n.version, n.notes) for n in skipped.notes] == [
        ("1.2.0", "New in 1.2.0"),
        ("1.1.2", "تازه‌های ۱٫۱٫۲"),
    ]
    assert [n.version for n in reader.execute("1.2.0", "en").notes] == []
    assert [n.version for n in reader.execute(None, "en").notes] == ["1.2.0"]


def test_github_releases_skip_drafts_and_pre_releases() -> None:
    payload = [
        {"tag_name": "v1.3.0-rc1", "prerelease": True},
        {"tag_name": "v1.2.0", "draft": True},
        {
            "tag_name": "v1.1.2",
            "html_url": "https://github.test/v1.1.2",
            "published_at": "2026-10-23T08:00:00Z",
            "body": "notes",
        },
        {"tag_name": "nightly"},
    ]
    response = httpx.Response(
        200, json=payload, request=httpx.Request("GET", "https://api.github.com")
    )
    with patch("httpx.get", return_value=response) as get:
        releases = GitHubReleaseFeed("1.1.1", "owner/repo").releases()
    assert [(r.version, r.body) for r in releases] == [("1.1.2", "notes")]
    assert releases[0].published_at == datetime(2026, 10, 23, 8, tzinfo=UTC)
    assert get.call_args.kwargs["headers"]["User-Agent"] == "ParsRAG/1.1.1"


def test_routes_report_updates_and_notes(tmp_path: Path) -> None:
    app.dependency_overrides[get_check_for_updates] = lambda: CheckForUpdates(
        Feed(["9.9.9"]), "1.1.1", lambda: True, Clock()
    )
    app.dependency_overrides[get_read_release_notes] = lambda: ReadReleaseNotes(
        _notes(tmp_path), "1.1.2"
    )
    try:
        client = TestClient(app)
        status = client.get("/updates").json()
        notes = client.get(
            "/release-notes", params={"since": "1.1.1", "language": "en"}
        ).json()
    finally:
        app.dependency_overrides.clear()
    assert status["latest_version"] == "9.9.9" and status["update_available"]
    assert notes == {
        "current_version": "1.1.2",
        "notes": [{"version": "1.1.2", "notes": "New in 1.1.2"}],
    }


@pytest.mark.parametrize("value", ["0", "false", "off"])
def test_the_setting_turns_the_check_off(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    from backend.api.dependencies import _update_check_enabled

    monkeypatch.setenv("UPDATE_CHECK_ENABLED", value)
    assert not _update_check_enabled()
    monkeypatch.setenv("UPDATE_CHECK_ENABLED", "1")
    assert _update_check_enabled()
