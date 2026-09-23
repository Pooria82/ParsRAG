from unittest.mock import MagicMock, patch

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.core.exceptions import VectorDBConnectionError
from backend.core.models.domain import ExtractedNode
from backend.infrastructure.database.qdrant_repo import QdrantRepository


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_qdrant_save_nodes(
    mock_settings: MagicMock, mock_qdrant_client_cls: MagicMock
) -> None:
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client

    # Mock embeddings
    mock_settings.embed_model.get_text_embedding_batch.return_value = [
        [0.1] * 768,
        [0.2] * 768,
    ]

    repo = QdrantRepository(collection_name="test_collection", vector_size=768)

    nodes = [
        ExtractedNode(text="Chunk 1", metadata={"page": 1}),
        ExtractedNode(text="Chunk 2", metadata={"page": 2}),
    ]

    repo.save_nodes(nodes, session_id="test_session")

    # Assert client.upsert was called
    mock_client.upsert.assert_called_once()
    _, kwargs = mock_client.upsert.call_args
    assert kwargs["collection_name"] == "test_collection"
    assert len(kwargs["points"]) == 2
    assert kwargs["points"][0].payload["session_id"] == "test_session"
    assert kwargs["points"][0].payload["text"] == "Chunk 1"


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_qdrant_save_nodes_bounds_embedding_and_upsert_batches(
    mock_settings: MagicMock,
    mock_qdrant_client_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Large documents cannot create one unbounded embedding allocation."""
    monkeypatch.setenv("QDRANT_UPSERT_BATCH_SIZE", "2")
    mock_client = mock_qdrant_client_cls.return_value
    mock_settings.embed_model.get_text_embedding_batch.side_effect = lambda texts: [
        [0.1] * 3 for _ in texts
    ]
    repo = QdrantRepository(collection_name="bounded", vector_size=3)
    nodes = [ExtractedNode(text=f"chunk-{index}") for index in range(5)]

    repo.save_nodes(nodes, session_id="session")

    assert [
        len(call.kwargs["points"]) for call in mock_client.upsert.call_args_list
    ] == [2, 2, 1]
    assert [
        len(call.args[0])
        for call in mock_settings.embed_model.get_text_embedding_batch.call_args_list
    ] == [2, 2, 1]


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_qdrant_similarity_search(
    mock_settings: MagicMock, mock_qdrant_client_cls: MagicMock
) -> None:
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client

    mock_settings.embed_model.get_text_embedding.return_value = [0.1] * 768

    mock_point = MagicMock()
    mock_point.payload = {"text": "Found text", "page": 1}
    mock_point.score = 0.95

    mock_query_result = MagicMock()
    mock_query_result.points = [mock_point]
    mock_client.query_points.return_value = mock_query_result

    repo = QdrantRepository(collection_name="test_collection", vector_size=768)
    results = repo.similarity_search("query", top_k=1, session_id="test_session")

    assert len(results) == 1
    assert results[0].text == "Found text"
    assert results[0].score == 0.95
    assert results[0].metadata == {"page": 1}

    mock_client.query_points.assert_called_once()
    _, kwargs = mock_client.query_points.call_args
    assert kwargs["collection_name"] == "test_collection"
    assert kwargs["limit"] == 1
    session_condition = kwargs["query_filter"].must[0]
    assert session_condition.match.value == "test_session"


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
def test_qdrant_delete_session(mock_qdrant_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client

    repo = QdrantRepository(collection_name="test_collection", vector_size=768)
    repo.delete_session("test_session")

    mock_client.delete.assert_called_once()
    _, kwargs = mock_client.delete.call_args
    assert kwargs["collection_name"] == "test_collection"


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
def test_qdrant_delete_document_scopes_session_and_filename(
    mock_qdrant_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client
    repo = QdrantRepository(collection_name="test_collection", vector_size=768)

    repo.delete_document("session-one", "guide.pdf")

    selector = mock_client.delete.call_args.kwargs["points_selector"]
    assert len(selector.filter.must) == 2


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_empty_file_filter_returns_no_results_without_embedding(
    mock_settings: MagicMock, mock_qdrant_client_cls: MagicMock
) -> None:
    repo = QdrantRepository(collection_name="test_collection", vector_size=768)
    assert repo.similarity_search("query", file_filter=[]) == []
    mock_settings.embed_model.get_text_embedding.assert_not_called()


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_collection_dimension_comes_from_embedding_model(
    mock_settings: MagicMock, mock_qdrant_client_cls: MagicMock
) -> None:
    """New collections use the active embedding model's actual vector size."""
    mock_client = mock_qdrant_client_cls.return_value
    mock_client.collection_exists.return_value = False
    mock_settings.embed_model.get_text_embedding.return_value = [0.1, 0.2, 0.3]

    QdrantRepository(collection_name="dimension_test")

    params = mock_client.create_collection.call_args.kwargs["vectors_config"]
    assert params.size == 3


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
def test_existing_collection_rejects_embedding_dimension_mismatch(
    mock_qdrant_client_cls: MagicMock,
) -> None:
    """An incompatible collection fails clearly instead of corrupting retrieval."""
    from qdrant_client.http import models as qmodels

    mock_client = mock_qdrant_client_cls.return_value
    mock_client.collection_exists.return_value = True
    mock_client.get_collection.return_value.config.params.vectors = (
        qmodels.VectorParams(size=384, distance=qmodels.Distance.COSINE)
    )

    with pytest.raises(VectorDBConnectionError, match="does not match"):
        QdrantRepository(
            collection_name="dimension_test",
            vector_size=768,
        )


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
def test_session_file_listing_scrolls_every_page(
    mock_qdrant_client_cls: MagicMock,
) -> None:
    """File discovery continues until Qdrant returns no next-page offset."""
    mock_client = mock_qdrant_client_cls.return_value
    first = MagicMock(payload={"filename": "a.pdf"})
    second = MagicMock(payload={"filename": "b.pdf"})
    mock_client.scroll.side_effect = [([first], 42), ([second], None)]
    repo = QdrantRepository(collection_name="test_collection", vector_size=768)

    assert repo.get_session_files("session-123") == ["a.pdf", "b.pdf"]
    assert mock_client.scroll.call_count == 2
    assert mock_client.scroll.call_args_list[1].kwargs["offset"] == 42


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_document_copy_reuses_vectors_in_bounded_pages(
    mock_settings: MagicMock, mock_qdrant_client_cls: MagicMock
) -> None:
    """A reused file retains evidence and vectors without re-embedding it."""
    source_point = MagicMock(
        id="source-id",
        vector=[0.2, 0.8],
        payload={
            "session_id": "old",
            "filename": "guide.pdf",
            "text": "evidence",
            "page": 3,
        },
    )
    client = mock_qdrant_client_cls.return_value
    client.scroll.side_effect = [([source_point], 77), ([], None)]
    repo = QdrantRepository(collection_name="test", vector_size=2)

    assert repo.copy_document("old", "new", "guide.pdf") == 1

    copied = client.upsert.call_args.kwargs["points"][0]
    assert copied.id != source_point.id
    assert copied.vector == source_point.vector
    assert copied.payload == {**source_point.payload, "session_id": "new"}
    assert client.scroll.call_args_list[1].kwargs["offset"] == 77
    assert client.upsert.call_args.kwargs["wait"] is True
    mock_settings.embed_model.get_text_embedding_batch.assert_not_called()


def test_document_copy_is_searchable_in_target_session() -> None:
    """Exercise Qdrant's actual local engine, including payload and vector copies."""
    client = QdrantClient(location=":memory:")
    client.create_collection(
        collection_name="reuse_test",
        vectors_config=qmodels.VectorParams(size=2, distance=qmodels.Distance.COSINE),
    )
    client.upsert(
        collection_name="reuse_test",
        points=[
            qmodels.PointStruct(
                id=1,
                vector=[0.2, 0.8],
                payload={
                    "session_id": "source",
                    "filename": "guide.pdf",
                    "text": "evidence",
                },
            )
        ],
    )
    repo = object.__new__(QdrantRepository)
    repo.client = client
    repo.collection_name = "reuse_test"

    assert repo.copy_document("source", "target", "guide.pdf") == 1
    assert repo.get_session_files("target") == ["guide.pdf"]
    source, _ = client.scroll(
        collection_name="reuse_test",
        scroll_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="session_id", match=qmodels.MatchValue(value="source")
                )
            ]
        ),
        with_vectors=True,
    )
    target, _ = client.scroll(
        collection_name="reuse_test",
        scroll_filter=qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="session_id", match=qmodels.MatchValue(value="target")
                )
            ]
        ),
        with_vectors=True,
    )
    assert len(source) == len(target) == 1
    assert target[0].id != source[0].id
    assert target[0].vector == pytest.approx(source[0].vector)
    assert target[0].payload == {**(source[0].payload or {}), "session_id": "target"}
