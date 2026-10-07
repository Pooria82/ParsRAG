"""Process-local capacity controls for expensive workstation operations."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import BoundedSemaphore

from backend.core.domain.exceptions import CapacityExceededError


class WorkLimiter:
    """Reject work immediately when every configured execution slot is occupied."""

    def __init__(self, slots: int, operation: str) -> None:
        """Initialize a positive number of slots for one operation type."""
        self._semaphore = BoundedSemaphore(max(1, slots))
        self._operation = operation

    @contextmanager
    def slot(self) -> Iterator[None]:
        """Reserve one slot or raise an explicit overload error."""
        if not self._semaphore.acquire(blocking=False):
            raise CapacityExceededError(
                f"The {self._operation} capacity is currently full. Try again shortly."
            )
        try:
            yield
        finally:
            self._semaphore.release()
