"""Session identity rules shared by every session-scoped use case."""

import re

SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
INVALID_SESSION_ID_MESSAGE = (
    "Invalid session_id format. Must be 1-64 alphanumeric characters, "
    "hyphens, or underscores."
)


def is_valid_session_id(session_id: str) -> bool:
    """Return whether a value is a safe, bounded session identifier."""
    return SESSION_ID_PATTERN.fullmatch(session_id) is not None
