"""Streamed answers: event order, refusals, slot release, and errors."""

import json
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from llama_index.core.llms import ChatMessage

from backend.api.dependencies import get_answer_query
from backend.core.domain.documents import ExtractedNode
from backend.core.domain.enums import QueryMode
from backend.core.domain.exceptions import CapacityExceededError
from backend.core.dto.input.query import QueryRequest
from backend.core.dto.output.query import PreparedAnswer
from backend.core.runtime.capacity import WorkLimiter
from backend.core.runtime.query_progress import InMemoryQueryProgress
from backend.core.strategies.generation import GeneratingStrategy
from backend.core.use_case.query.answer_query import AnswerQuery
from backend.main import app
from backend.tests.core.use_case.fakes import InMemoryRepository

SOURCES = [
    ExtractedNode(text="first", metadata={"filename": "a.pdf", "page": 1}),
    ExtractedNode(text="second", metadata={"filename": "a.pdf", "page": 2}),
]


class Condenser:
    """Return the question unchanged."""

    def condense(self, query: str, chat_history: list[ChatMessage]) -> str:
        """Echo the question."""
        return query


class StreamingStrategy:
    """Prepare a fixed prompt (or refusal) and stream preset deltas."""

    def __init__(
        self, deltas: list[str], prepared: PreparedAnswer | None = None
    ) -> None:
        """Keep deltas and the prepared answer."""
        self.deltas = deltas
        self.prepared = prepared or PreparedAnswer(prompt="p", sources=SOURCES)
        self.closed = False

    def prepare(self, **kwargs: Any) -> PreparedAnswer:
        """Return the preset preparation."""
        return self.prepared

    def stream(self, prepared: PreparedAnswer) -> Iterator[str]:
        """Yield deltas; "!" simulates a stalled model."""
        try:
            for delta in self.deltas:
                if delta == "!":
                    raise TimeoutError("model stalled")
                yield delta
        finally:
            self.closed = True


def _use_case(strategy: StreamingStrategy, limiter: WorkLimiter) -> AnswerQuery:
    return AnswerQuery(
        repository=InMemoryRepository(),
        condenser_factory=Condenser,
        strategy_resolver=lambda mode: strategy,  # type: ignore[arg-type,return-value]
        progress=InMemoryQueryProgress(),
        limiter=limiter,
    )


def _request(mode: QueryMode = QueryMode.STRICT) -> QueryRequest:
    return QueryRequest(prompt="هدف پروژه چیست؟", mode=mode, session_id="session-1")


def test_events_arrive_as_stages_sources_tokens_then_result() -> None:
    strategy = StreamingStrategy(["هدف ", "ساخت سامانه است ", "[2]."])
    events = list(_use_case(strategy, WorkLimiter(1, "query")).stream(_request()))

    kinds = [event.kind for event in events]
    assert kinds == [
        "stage",
        "stage",
        "sources",
        "stage",
        "token",
        "token",
        "token",
        "done",
    ]
    assert [event.data.get("stage") for event in events if event.kind == "stage"] == [
        "understanding",
        "retrieving",
        "generating",
    ]
    done = events[-1].data
    assert done["answer"] == "هدف ساخت سامانه است [2]."
    assert done["cited"] == [2]
    assert [node["text"] for node in done["source_nodes"]] == ["first", "second"]


def test_refusals_finish_without_sources_or_generation() -> None:
    strategy = StreamingStrategy(
        ["never"], PreparedAnswer(immediate="no evidence", outcome="no_evidence")
    )
    events = list(_use_case(strategy, WorkLimiter(1, "query")).stream(_request()))

    assert [event.kind for event in events] == ["stage", "stage", "done"]
    assert events[-1].data["outcome"] == "no_evidence"
    assert events[-1].data["source_nodes"] == []


def test_llm_only_skips_the_retrieval_stage() -> None:
    strategy = StreamingStrategy(["hi"], PreparedAnswer(prompt="p"))
    events = list(
        _use_case(strategy, WorkLimiter(1, "query")).stream(
            _request(QueryMode.LLM_ONLY)
        )
    )
    stages = [event.data["stage"] for event in events if event.kind == "stage"]
    assert stages == ["understanding", "generating"]


def test_closing_the_stream_stops_generation_and_frees_the_slot() -> None:
    """A client that disconnects mid-answer does not keep the model busy."""
    limiter = WorkLimiter(1, "query")
    strategy = StreamingStrategy(["a", "b", "c"])
    stream = _use_case(strategy, limiter).stream(_request())
    while next(stream).kind != "token":
        pass
    stream.close()

    assert strategy.closed
    with limiter.slot():
        pass


def test_a_busy_service_is_reported_when_the_stream_starts() -> None:
    limiter = WorkLimiter(1, "query")
    with limiter.slot(), pytest.raises(CapacityExceededError):
        next(_use_case(StreamingStrategy(["a"]), limiter).stream(_request()))


def _sse(body: str) -> list[tuple[str, Any]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((lines["event"], json.loads(lines["data"])))
    return events


def test_route_streams_server_sent_events_and_reports_late_errors() -> None:
    strategy = StreamingStrategy(["partial ", "!"])
    app.dependency_overrides[get_answer_query] = lambda: _use_case(
        strategy, WorkLimiter(1, "query")
    )
    try:
        response = TestClient(app).post(
            "/query/stream",
            json={"prompt": "سلام", "mode": "strict", "session_id": "session-1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _sse(response.text)
    assert events[-2] == ("token", {"text": "partial "})
    assert events[-1] == (
        "error",
        {"detail": "The model did not answer in time.", "code": "model_timeout"},
    )


def test_strategies_stream_model_deltas() -> None:
    class Strategy(GeneratingStrategy):
        def __init__(self) -> None:
            self.llm = MagicMock()
            self.llm.stream_complete.return_value = iter(
                [
                    MagicMock(delta="سلام"),
                    MagicMock(delta=None),
                    MagicMock(delta=" دنیا"),
                ]
            )

    strategy = Strategy()
    assert list(strategy.stream(PreparedAnswer(prompt="p"))) == ["سلام", " دنیا"]
    assert list(strategy.stream(PreparedAnswer(immediate="x"))) == []
    with pytest.raises(NotImplementedError):
        strategy.prepare("q", [])
