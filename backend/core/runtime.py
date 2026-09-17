"""Thread-safe application readiness state."""

from __future__ import annotations

from threading import Lock


class RuntimeState:
    """Track model and storage initialization without exposing internal errors."""

    def __init__(self) -> None:
        """Start in the preparing state."""
        self._lock = Lock()
        self._status = "preparing"

    def mark_ready(self) -> None:
        """Mark every required runtime adapter as ready."""
        with self._lock:
            self._status = "ready"

    def mark_failed(self) -> None:
        """Mark initialization as failed without retaining sensitive details."""
        with self._lock:
            self._status = "failed"

    def status(self) -> str:
        """Return the current public readiness state."""
        with self._lock:
            return self._status

    def is_ready(self) -> bool:
        """Return whether query and ingestion work may begin."""
        return self.status() == "ready"


runtime_state = RuntimeState()
