"""Query use-case orchestration exercised with port fakes."""

from typing import Any
from uuid import UUID

import pytest
from llama_index.core.llms import ChatMessage

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.enums import QueryMode
from backend.core.domain.exceptions import InvalidInputError, NotFoundError
from backend.core.dto.input.query import QueryRequest
from backend.core.dto.output.query import QueryResponse
from backend.core.runtime.capacity import WorkLimiter
from backend.core.runtime.query_progress import InMemoryQueryProgress
from backend.core.use_case.query.answer_query import AnswerQuery
from backend.core.use_case.query.read_query_progress import ReadQueryProgress
from backend.tests.core.use_case.fakes import InMemoryRepository

REQUEST_ID = UUID("4df43765-52bf-4d3e-b8df-530596aacd84")


class EchoCondenser:
    """Prefix the query so tests can see condensation happened."""

    def condense(self, query: str, chat_history: list[ChatMessage]) -> str:
        """Return a marked standalone question."""
        return f"standalone: {query}" if chat_history else query


class RecordingStrategy:
    """Capture execute keyword arguments and optionally report progress."""

    def __init__(self, fail: bool = False) -> None:
        """Configure whether execution raises."""
        self.fail = fail
        self.calls: list[dict[str, Any]] = []

    def execute(self, **kwargs: Any) -> QueryResponse:
        """Record the call, report retrieval, and answer."""
        self.calls.append(kwargs)
        if kwargs.get("progress"):
            kwargs["progress"]("retrieving")
        if self.fail:
            raise RuntimeError("model failed")
        return QueryResponse(answer="answer", source_nodes=[])


def _use_case(
    strategy: RecordingStrategy,
    progress: InMemoryQueryProgress,
    repository: InMemoryRepository,
) -> AnswerQuery:
    return AnswerQuery(
        repository=repository,
        condenser_factory=EchoCondenser,
        strategy_resolver=lambda mode: strategy,  # type: ignore[arg-type,return-value]
        progress=progress,
        limiter=WorkLimiter(1, "query"),
    )


def test_condenses_history_and_publishes_completion(
    repository: InMemoryRepository,
) -> None:
    strategy = RecordingStrategy()
    progress = InMemoryQueryProgress()
    request = QueryRequest(
        prompt="and its price?",
        chat_history=[{"role": "user", "content": "What is the product?"}],  # type: ignore[list-item]
        session_id="session-1",
        request_id=REQUEST_ID,
    )

    response = _use_case(strategy, progress, repository).execute(request)

    assert response.answer == "answer"
    assert strategy.calls[0]["query"] == "standalone: and its price?"
    assert "document_segments" not in strategy.calls[0]
    assert ReadQueryProgress(progress).execute(REQUEST_ID).stage == "complete"


def test_failures_publish_failed_stage(repository: InMemoryRepository) -> None:
    progress = InMemoryQueryProgress()
    request = QueryRequest(prompt="q", session_id="s", request_id=REQUEST_ID)

    with pytest.raises(RuntimeError):
        _use_case(RecordingStrategy(fail=True), progress, repository).execute(request)

    assert progress.get_stage(str(REQUEST_ID)) == "failed"


def test_without_request_id_progress_is_not_sent(
    repository: InMemoryRepository,
) -> None:
    strategy = RecordingStrategy()

    _use_case(strategy, InMemoryQueryProgress(), repository).execute(
        QueryRequest(prompt="q", session_id="s")
    )

    assert "progress" not in strategy.calls[0]


def test_mentions_resolve_against_filtered_session_files(
    repository: InMemoryRepository,
) -> None:
    repository.save_nodes(
        [
            ExtractedNode(text="a", metadata={"filename": "a.pdf"}),
            ExtractedNode(text="b", metadata={"filename": "b.pdf"}),
        ],
        "s",
    )
    strategy = RecordingStrategy()
    use_case = _use_case(strategy, InMemoryQueryProgress(), repository)

    use_case.execute(QueryRequest(prompt="Summarize @{a.pdf}", session_id="s"))
    assert strategy.calls[0]["document_segments"][0][0] == "a.pdf"

    with pytest.raises(InvalidInputError):
        use_case.execute(
            QueryRequest(
                prompt="Summarize @{a.pdf}", session_id="s", file_filter=["b.pdf"]
            )
        )


def test_llm_only_ignores_mentions(repository: InMemoryRepository) -> None:
    strategy = RecordingStrategy()

    _use_case(strategy, InMemoryQueryProgress(), repository).execute(
        QueryRequest(prompt="Explain @{missing.pdf}", mode=QueryMode.LLM_ONLY)
    )

    assert "document_segments" not in strategy.calls[0]


def test_unknown_progress_is_not_found() -> None:
    with pytest.raises(NotFoundError):
        ReadQueryProgress(InMemoryQueryProgress()).execute(REQUEST_ID)
