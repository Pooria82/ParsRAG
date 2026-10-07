"""FlashRank adapter: configuration, scoring order, and offline fallback."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.core.domain.documents import ExtractedNode
from backend.infrastructure.llm.reranker import (
    DEFAULT_RERANK_MODEL,
    FlashRankReranker,
    configured_rerank_model,
    rerank_cache_dir,
)


def _nodes() -> list[ExtractedNode]:
    return [
        ExtractedNode(text="weak", metadata={"filename": "a.pdf"}, score=0.6),
        ExtractedNode(text="strong", metadata={"filename": "b.pdf"}, score=0.9),
        ExtractedNode(text="middle", metadata={"filename": "a.pdf"}, score=0.7),
    ]


def test_model_and_cache_come_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operators can choose or disable the model and move its cache."""
    monkeypatch.delenv("RERANK_MODEL", raising=False)
    monkeypatch.delenv("RERANK_CACHE_DIR", raising=False)
    assert configured_rerank_model() == DEFAULT_RERANK_MODEL
    assert rerank_cache_dir() == Path.home() / ".cache" / "flashrank"

    monkeypatch.setenv("RERANK_MODEL", "off")
    monkeypatch.setenv("RERANK_CACHE_DIR", "/models/rerank")
    assert configured_rerank_model() is None
    assert rerank_cache_dir() == Path("/models/rerank")


def test_cross_encoder_scores_replace_dense_order() -> None:
    """Passages are ranked by the cross-encoder and keep their metadata."""
    ranker = MagicMock()
    ranker.rerank.return_value = [
        {"id": 2, "score": 0.99},
        {"id": 0, "score": 0.5},
        {"id": 1, "score": 0.1},
    ]
    with patch("backend.infrastructure.llm.reranker._load_ranker", return_value=ranker):
        ranked = FlashRankReranker("model").rerank("question", _nodes(), top_n=2)

    assert [(node.text, node.score) for node in ranked] == [
        ("middle", 0.99),
        ("weak", 0.5),
    ]
    assert ranked[0].metadata == {"filename": "a.pdf"}
    request = ranker.rerank.call_args.args[0]
    assert request.query == "question"
    assert [passage["text"] for passage in request.passages] == [
        "weak",
        "strong",
        "middle",
    ]


def test_unavailable_model_falls_back_to_dense_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An offline first start answers with vector order instead of failing."""
    with patch(
        "backend.infrastructure.llm.reranker._load_ranker",
        side_effect=OSError("no network"),
    ):
        reranker = FlashRankReranker("model")
        ranked = reranker.rerank("question", _nodes(), top_n=2)
        assert not reranker.warm_up()

    assert [node.text for node in ranked] == ["strong", "middle"]
    assert "reranker_unavailable" in caplog.text


def test_disabled_reranker_never_loads_a_model() -> None:
    """RERANK_MODEL=none keeps dense order without touching FlashRank."""
    with patch("backend.infrastructure.llm.reranker._load_ranker") as load:
        reranker = FlashRankReranker(None)
        ranked = reranker.rerank("question", _nodes(), top_n=5)

    load.assert_not_called()
    assert [node.text for node in ranked] == ["strong", "middle", "weak"]
    assert reranker.rerank("question", [], top_n=3) == []
