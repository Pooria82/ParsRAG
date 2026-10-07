"""Operator retrieval settings: threshold default and depth precedence."""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.domain.documents import ExtractedNode
from backend.core.service.retrieval_optimizer import configured_depth
from backend.core.strategies.hybrid_rag import HybridRAGStrategy
from backend.core.strategies.strict_rag import (
    DEFAULT_STRICT_THRESHOLD,
    StrictRAGStrategy,
)

DEPTH_VARIABLES = (
    "RAG_TOP_K",
    "STRICT_RAG_TOP_K",
    "HYBRID_RERANK_TOP_K",
    "HYBRID_RETRIEVE_TOP_K",
    "STRICT_RAG_THRESHOLD",
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test without retrieval overrides."""
    for name in DEPTH_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({}, None),
        ({"STRICT_RAG_TOP_K": ""}, None),
        ({"STRICT_RAG_TOP_K": "  "}, None),
        ({"STRICT_RAG_TOP_K": "not-a-number"}, None),
        ({"STRICT_RAG_TOP_K": "12"}, 12),
        ({"STRICT_RAG_TOP_K": "0"}, 1),
        ({"STRICT_RAG_TOP_K": "500"}, 50),
        ({"RAG_TOP_K": "9"}, 9),
        ({"STRICT_RAG_TOP_K": "7", "RAG_TOP_K": "9"}, 7),
    ],
)
def test_configured_depth_precedence_and_bounds(
    monkeypatch: pytest.MonkeyPatch, values: dict[str, str], expected: int | None
) -> None:
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    assert configured_depth("STRICT_RAG_TOP_K", "RAG_TOP_K") == expected


def _node(score: float) -> ExtractedNode:
    return ExtractedNode(
        text="The invoice total is 425 euros.",
        metadata={"filename": "invoice.pdf", "page": 1},
        score=score,
    )


@patch("backend.core.strategies.strict_rag.Settings")
def test_strict_threshold_default_matches_compose(
    mock_settings: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert StrictRAGStrategy(MagicMock()).threshold == DEFAULT_STRICT_THRESHOLD == 0.80
    monkeypatch.setenv("STRICT_RAG_THRESHOLD", "0.65")
    assert StrictRAGStrategy(MagicMock()).threshold == 0.65


@pytest.mark.parametrize(
    ("environment", "request_top_k", "expected_depth"),
    [
        ({}, None, "adaptive"),
        ({"STRICT_RAG_TOP_K": "6"}, None, 6),
        ({"RAG_TOP_K": "4"}, None, 4),
        ({"STRICT_RAG_TOP_K": "6"}, 3, 3),
    ],
)
@patch("backend.core.strategies.strict_rag.Settings")
def test_strict_depth_precedence(
    mock_settings: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str],
    request_top_k: int | None,
    expected_depth: int | str,
) -> None:
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    repo = MagicMock()
    repo.get_session_files.return_value = ["invoice.pdf"]
    repo.similarity_search.return_value = [_node(0.9)]
    mock_settings.llm.complete.return_value = "425 euros"

    with patch(
        "backend.core.strategies.strict_rag.RetrievalOptimizer.calculate_optimal_depth",
        return_value=17,
    ):
        StrictRAGStrategy(repo).execute(
            "What is the invoice total?", [], session_id="s", top_k=request_top_k
        )

    depth = repo.similarity_search.call_args.kwargs["top_k"]
    assert depth == (17 if expected_depth == "adaptive" else expected_depth)


@pytest.mark.parametrize(
    ("environment", "expected_rerank"),
    [({}, 17), ({"HYBRID_RERANK_TOP_K": "5"}, 5)],
)
@patch("backend.core.strategies.hybrid_rag.FlashRankRerank")
@patch("backend.core.strategies.hybrid_rag.Settings")
def test_hybrid_rerank_depth_uses_configuration_or_adaptive(
    mock_settings: MagicMock,
    mock_reranker: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    environment: dict[str, str],
    expected_rerank: int,
) -> None:
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    repo = MagicMock()
    repo.get_session_files.return_value = ["invoice.pdf"]
    repo.similarity_search.return_value = [_node(0.9)]
    mock_reranker.return_value.postprocess_nodes.return_value = []
    mock_settings.llm.complete.return_value = "answer"

    with patch(
        "backend.core.strategies.hybrid_rag.RetrievalOptimizer.calculate_optimal_depth",
        return_value=17,
    ):
        HybridRAGStrategy(repo).execute(
            "What is the invoice total?", [], session_id="s"
        )

    mock_reranker.assert_called_with(top_n=expected_rerank)
    retrieve_k = repo.similarity_search.call_args.kwargs["top_k"]
    assert retrieve_k == max(expected_rerank * 2, 25)
