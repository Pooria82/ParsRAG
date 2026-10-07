"""Request correlation identifiers shared by adapters and operation logs."""

from contextvars import ContextVar, Token

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def current_correlation_id() -> str | None:
    """Expose the active request ID to downstream adapters and operation logs."""
    return _correlation_id.get()


def bind_correlation_id(correlation_id: str) -> Token[str | None]:
    """Bind an ID to the current execution context and return its reset token."""
    return _correlation_id.set(correlation_id)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the correlation ID that was active before ``bind_correlation_id``."""
    _correlation_id.reset(token)
