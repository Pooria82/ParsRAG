"""Thread-safe, short-lived progress state for in-flight local queries."""

from collections.abc import Callable
from threading import Lock
from time import monotonic
from typing import Literal

QueryStage = Literal["understanding", "retrieving", "generating", "complete", "failed"]
ProgressCallback = Callable[[QueryStage], None]

_TTL_SECONDS = 300.0
_stages: dict[str, tuple[QueryStage, float]] = {}
_lock = Lock()


def set_query_stage(request_id: str, stage: QueryStage) -> None:
    """Record a non-sensitive query stage and prune expired entries."""
    now = monotonic()
    with _lock:
        expired = [
            key for key, (_, updated) in _stages.items() if now - updated > _TTL_SECONDS
        ]
        for key in expired:
            del _stages[key]
        _stages[request_id] = (stage, now)


def get_query_stage(request_id: str) -> QueryStage | None:
    """Return an active stage without exposing prompts or document content."""
    now = monotonic()
    with _lock:
        record = _stages.get(request_id)
        if record is None:
            return None
        stage, updated = record
        if now - updated > _TTL_SECONDS:
            del _stages[request_id]
            return None
        return stage
