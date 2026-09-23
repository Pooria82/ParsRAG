from backend.core.runtime import RuntimeState


def test_runtime_state_hides_failure_details() -> None:
    """Readiness exposes only a small public state machine."""
    state = RuntimeState()
    assert state.status() == "preparing"
    state.mark_failed()
    assert state.status() == "failed"
    state.mark_ready()
    assert state.is_ready() is True
