"""Bounded per-session mutation locks."""

from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from threading import Lock


class SessionLocks:
    """Serialize mutations of one session without retaining unbounded lock keys.

    Sessions hash onto a fixed stripe of locks; unrelated sessions may share a
    stripe, which only costs concurrency, never correctness.
    """

    def __init__(self, stripes: int = 64) -> None:
        """Allocate a fixed number of lock stripes."""
        self._locks = tuple(Lock() for _ in range(max(1, stripes)))

    def lock_for(self, session_id: str) -> Lock:
        """Return the stripe guarding ``session_id``."""
        return self._locks[hash(session_id) % len(self._locks)]

    @contextmanager
    def hold(self, *session_ids: str) -> Iterator[None]:
        """Hold every stripe for the given sessions in a deadlock-free order."""
        locks = sorted(
            {self.lock_for(session_id) for session_id in session_ids}, key=id
        )
        with ExitStack() as stack:
            for lock in locks:
                stack.enter_context(lock)
            yield
