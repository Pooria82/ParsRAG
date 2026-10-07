"""Thread-safe, short-lived progress state for in-flight local queries."""

from threading import Lock
from time import monotonic

from backend.core.domain.enums import QueryStage

_TTL_SECONDS = 300.0


class InMemoryQueryProgress:
    """Process-local ``ProgressTracker`` that forgets stages after a short TTL."""

    def __init__(self, ttl_seconds: float = _TTL_SECONDS) -> None:
        """Create an empty store whose entries expire after ``ttl_seconds``."""
        self._ttl_seconds = ttl_seconds
        self._stages: dict[str, tuple[QueryStage, float]] = {}
        self._lock = Lock()

    def set_stage(self, request_id: str, stage: QueryStage) -> None:
        """Record a non-sensitive query stage and prune expired entries."""
        now = monotonic()
        with self._lock:
            expired = [
                key
                for key, (_, updated) in self._stages.items()
                if now - updated > self._ttl_seconds
            ]
            for key in expired:
                del self._stages[key]
            self._stages[request_id] = (stage, now)

    def get_stage(self, request_id: str) -> QueryStage | None:
        """Return an active stage without exposing prompts or document content."""
        now = monotonic()
        with self._lock:
            record = self._stages.get(request_id)
            if record is None:
                return None
            stage, updated = record
            if now - updated > self._ttl_seconds:
                del self._stages[request_id]
                return None
            return stage


query_progress = InMemoryQueryProgress()
