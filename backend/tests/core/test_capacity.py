import pytest

from backend.core.domain.exceptions import CapacityExceededError
from backend.core.runtime.capacity import WorkLimiter


def test_work_limiter_rejects_saturation_without_waiting() -> None:
    """A full workstation queue returns an explicit overload response."""
    limiter = WorkLimiter(1, "query")

    with limiter.slot(), pytest.raises(CapacityExceededError) as error, limiter.slot():
        pass

    assert "query capacity is currently full" in str(error.value.detail)
