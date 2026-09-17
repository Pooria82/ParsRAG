import pytest
from fastapi import HTTPException

from backend.core.capacity import WorkLimiter


def test_work_limiter_rejects_saturation_without_waiting() -> None:
    """A full workstation queue returns an explicit overload response."""
    limiter = WorkLimiter(1, "query")

    with limiter.slot(), pytest.raises(HTTPException) as error, limiter.slot():
        pass

    assert error.value.status_code == 429
