"""Startup retries transient failures instead of staying unready until a restart."""

from unittest.mock import MagicMock

import pytest

import backend.api.dependencies as dependencies
import backend.main as main
from backend.core.runtime.readiness import RuntimeState


@pytest.fixture
def state(monkeypatch: pytest.MonkeyPatch) -> RuntimeState:
    fresh = RuntimeState()
    monkeypatch.setattr(main, "runtime_state", fresh)
    reranker = MagicMock()
    monkeypatch.setattr(dependencies, "reranker", reranker)
    return fresh


def test_a_transient_failure_is_retried_until_ready(
    state: RuntimeState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Qdrant timeout on the first try no longer leaves the service unready."""
    repository = MagicMock()
    repository.is_ready.side_effect = [TimeoutError("qdrant busy"), True]
    monkeypatch.setattr(main, "setup_llm_and_embeddings", MagicMock())
    monkeypatch.setattr(dependencies, "_shared_document_repository", lambda: repository)
    sleeps: list[float] = []

    main._initialize_runtime(delays=(5, 10), sleep=sleeps.append)

    assert state.status() == "ready"
    assert sleeps == [5]


def test_runtime_is_failed_after_the_last_retry(
    state: RuntimeState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Persistent failures still surface as a failed runtime."""
    monkeypatch.setattr(
        main,
        "setup_llm_and_embeddings",
        MagicMock(side_effect=RuntimeError("no model")),
    )
    sleeps: list[float] = []

    main._initialize_runtime(delays=(1, 2), sleep=sleeps.append, max_attempts=3)

    assert state.status() == "failed"
    assert sleeps == [1, 2]


def test_a_failed_runtime_keeps_retrying_and_recovers(
    state: RuntimeState, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After the delays run out, the last delay repeats until a start succeeds."""
    setup = MagicMock(side_effect=[RuntimeError("down")] * 5 + [None])
    monkeypatch.setattr(main, "setup_llm_and_embeddings", setup)
    repository = MagicMock()
    repository.is_ready.return_value = True
    monkeypatch.setattr(dependencies, "_shared_document_repository", lambda: repository)
    statuses: list[str] = []

    def sleep(seconds: float) -> None:
        statuses.append(f"{state.status()}:{seconds}")

    main._initialize_runtime(delays=(1, 2), sleep=sleep, max_attempts=10)

    assert state.status() == "ready"
    assert statuses == [
        "preparing:1",
        "preparing:2",
        "failed:2",
        "failed:2",
        "failed:2",
    ]
