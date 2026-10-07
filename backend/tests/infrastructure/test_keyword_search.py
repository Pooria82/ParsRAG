"""BM25 keyword matches fused with vector search."""

from unittest.mock import patch

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.core.domain.documents import ExtractedNode
from backend.infrastructure.database.keyword_index import (
    SessionCorpus,
    SessionCorpusCache,
    keyword_tokens,
)
from backend.infrastructure.database.qdrant_repo import QdrantRepository, fuse_rankings


def test_tokens_share_one_spelling_and_digit_form() -> None:
    assert keyword_tokens("نرم‌افزار Katalon با ۱۲ تست، كيفيت") == [
        "نرم",
        "افزار",
        "katalon",
        "با",
        "12",
        "تست",
        "کیفیت",
    ]


def test_rare_exact_terms_rank_first_and_filters_apply() -> None:
    corpus = SessionCorpus(
        ids=[1, 2, 3],
        texts=[
            "ابزارهای تست نرم‌افزار متنوع هستند",
            "Katalon Recorder برای تست رابط کاربری",
            "Katalon در گزارش دوم",
        ],
        payloads=[{"filename": "a"}, {"filename": "a"}, {"filename": "b"}],
    )

    ranked = corpus.search("Katalon تست", 5, lambda payload: True)
    only_a = corpus.search("Katalon", 5, lambda payload: payload["filename"] == "a")

    assert [index for index, _ in ranked][:1] == [1]
    assert [index for index, _ in only_a] == [1]
    assert corpus.search("واژه‌ای که نیست", 5, lambda payload: True) == []


def test_cache_drops_changed_sessions_and_stale_loads() -> None:
    cache = SessionCorpusCache(capacity=1)
    first = SessionCorpus(ids=[], texts=[], payloads=[])
    assert cache.get("s", lambda: first) is first
    assert cache.get("s", lambda: pytest.fail("cached")) is first

    cache.invalidate("s")
    second = SessionCorpus(ids=[], texts=[], payloads=[])

    def load_while_documents_change() -> SessionCorpus:
        cache.invalidate("s")
        return second

    assert cache.get("s", load_while_documents_change) is second
    third = SessionCorpus(ids=[], texts=[], payloads=[])
    assert cache.get("s", lambda: third) is third, "stale corpus must not be cached"
    cache.get("other", lambda: SessionCorpus(ids=[], texts=[], payloads=[]))
    assert cache.get("s", lambda: first) is first, "capacity evicts the oldest"


def test_reciprocal_rank_fusion_merges_and_deduplicates() -> None:
    a, b, c = (ExtractedNode(text=name) for name in "abc")
    fused = fuse_rankings([(1, a), (2, b)], [(3, c), (1, a)], limit=3)
    assert [node.text for node in fused] == ["a", "c", "b"]


@pytest.fixture
def repository(monkeypatch: pytest.MonkeyPatch) -> QdrantRepository:
    """A real local Qdrant engine with three chunks in one session."""
    monkeypatch.setenv("KEYWORD_SEARCH", "1")
    client = QdrantClient(location=":memory:")
    client.create_collection(
        collection_name="keyword_test",
        vectors_config=qmodels.VectorParams(size=2, distance=qmodels.Distance.COSINE),
    )
    chunks = [
        (1, [1.0, 0.0], "روش‌های کلی ارزیابی نرم‌افزار"),
        (2, [0.9, 0.1], "مستندات عمومی پروژه"),
        (3, [0.1, 0.9], "تست رابط کاربری با Katalon Recorder انجام شد"),
    ]
    client.upsert(
        collection_name="keyword_test",
        points=[
            qmodels.PointStruct(
                id=point_id,
                vector=vector,
                payload={"session_id": "s", "filename": "r.docx", "text": text},
            )
            for point_id, vector, text in chunks
        ],
    )
    repo = object.__new__(QdrantRepository)
    repo.client = client
    repo.collection_name = "keyword_test"
    return repo


def test_keyword_only_match_joins_results_with_its_cosine_score(
    repository: QdrantRepository,
) -> None:
    """An exact tool name outside the vector top-k is still retrieved."""
    with patch("backend.infrastructure.database.qdrant_repo.Settings") as settings:
        settings.embed_model.get_query_embedding.return_value = [1.0, 0.0]
        nodes = repository.similarity_search("Katalon", top_k=2, session_id="s")

    texts = [node.text for node in nodes]
    assert "تست رابط کاربری با Katalon Recorder انجام شد" in texts
    keyword_node = next(node for node in nodes if "Katalon" in node.text)
    assert keyword_node.score == pytest.approx(0.1104, abs=1e-3)
    assert keyword_node.metadata == {"filename": "r.docx"}


def test_new_chunks_are_searchable_after_the_cache_is_invalidated(
    repository: QdrantRepository,
) -> None:
    with patch("backend.infrastructure.database.qdrant_repo.Settings") as settings:
        settings.embed_model.get_query_embedding.return_value = [1.0, 0.0]
        settings.embed_model.get_text_embedding_batch.return_value = [[0.0, 1.0]]
        assert not any(
            "Appium" in node.text
            for node in repository.similarity_search("Appium", top_k=1, session_id="s")
        )
        repository.save_nodes(
            [ExtractedNode(text="Appium برای موبایل", metadata={"filename": "m.pdf"})],
            session_id="s",
        )
        nodes = repository.similarity_search("Appium", top_k=2, session_id="s")

    assert any("Appium" in node.text for node in nodes)


def test_keyword_fusion_can_be_disabled(
    repository: QdrantRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KEYWORD_SEARCH", "off")
    with patch("backend.infrastructure.database.qdrant_repo.Settings") as settings:
        settings.embed_model.get_query_embedding.return_value = [1.0, 0.0]
        nodes = repository.similarity_search("Katalon", top_k=2, session_id="s")
    assert all("Katalon" not in node.text for node in nodes)
