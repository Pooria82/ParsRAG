"""Use case: tell the user when a newer release is out."""

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from backend.core.domain.versioning import is_newer, parse_version
from backend.core.dto.output.updates import ReleaseSummary, UpdateStatusResponse
from backend.core.port.release_feed import ReleaseFeed

logger = logging.getLogger("parsrag.operations")

# A day between checks: the browser asks every 30 seconds, GitHub is asked once.
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
# "Check now" is honoured at most this often, within GitHub's anonymous limit.
MANUAL_CHECK_SECONDS = 60
# Notes are fetched for at most this many newer releases.
MAX_RELEASES = 5


class CheckForUpdates:
    """Compare the running version with the latest published release.

    The result is kept for a day; a failed check (offline) keeps the previous
    result and is retried at the next interval, so being offline never shows
    an error. Nothing about this installation is sent: it is one anonymous
    request for the public release list.
    """

    def __init__(
        self,
        feed: ReleaseFeed,
        current_version: str,
        enabled: Callable[[], bool],
        clock: Callable[[], float],
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        """Bind the release feed, the running version, and the on/off switch."""
        self._feed = feed
        self._current = current_version
        self._enabled = enabled
        self._clock = clock
        self._now = now
        self._lock = threading.Lock()
        self._checked: float | None = None
        self._checking = False
        self._result: UpdateStatusResponse | None = None

    def execute(self, refresh: bool = False) -> UpdateStatusResponse:
        """Return the update status, checking again when it is due.

        ``refresh`` asks again now, unless the last check was within a minute.
        """
        if not self._enabled():
            return UpdateStatusResponse(enabled=False, current_version=self._current)
        # GitHub is asked outside the lock: other requests meanwhile get the
        # last result instead of waiting up to a minute for a slow answer.
        with self._lock:
            age = None if self._checked is None else self._clock() - self._checked
            due = age is None or age >= CHECK_INTERVAL_SECONDS
            manual = refresh and age is not None and age >= MANUAL_CHECK_SECONDS
            start = (due or manual) and not self._checking
            if start:
                self._checking = True
                self._checked = self._clock()
        if start:
            fresh: UpdateStatusResponse | None = None
            try:
                fresh = self._check()
            finally:
                with self._lock:
                    self._result = fresh or self._result
                    self._checking = False
        with self._lock:
            return self._result or UpdateStatusResponse(
                enabled=True, current_version=self._current
            )

    def _check(self) -> UpdateStatusResponse | None:
        try:
            releases = self._feed.releases()
        except Exception as exc:  # noqa: BLE001 - offline or GitHub unavailable.
            logger.info("update_check_failed error=%s", type(exc).__name__)
            return None
        newer = [r for r in releases if is_newer(r.version, self._current)]
        newer.sort(
            key=lambda release: parse_version(release.version) or (0, 0, 0),
            reverse=True,
        )
        summaries = [
            ReleaseSummary(
                version=release.version,
                url=release.url,
                published_at=release.published_at,
                notes_fa=self._notes(release.version, "fa") or release.body,
                notes_en=self._notes(release.version, "en") or release.body,
            )
            for release in newer[:MAX_RELEASES]
        ]
        latest = summaries[0].version if summaries else self._current
        logger.info("update_check_complete current=%s latest=%s", self._current, latest)
        return UpdateStatusResponse(
            enabled=True,
            current_version=self._current,
            latest_version=latest,
            update_available=bool(summaries),
            checked_at=self._now(),
            releases=summaries,
        )

    def _notes(self, version: str, language: str) -> str | None:
        try:
            return self._feed.notes(version, "fa" if language == "fa" else "en")
        except Exception:  # noqa: BLE001 - the GitHub release text is the fallback.
            return None
