from unittest.mock import MagicMock, patch

import pytest
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.exceptions import VectorDBConnectionError
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
    """Upserts stay bounded; the embedding model batches the whole document."""
    monkeypatch.setenv("QDRANT_UPSERT_BATCH_SIZE", "2")
    mock_client = mock_qdrant_client_cls.return_value
    mock_settings.embed_model.get_text_embedding_batch.side_effect = lambda texts: [
        [0.1] * 3 for _ in texts
    ]
    repo = QdrantRepository(collection_name="bounded", vector_size=3)
    nodes = [ExtractedNode(text="x" * (5 - index)) for index in range(5)]

    repo.save_nodes(nodes, session_id="session")

    assert [
        len(call.kwargs["points"]) for call in mock_client.upsert.call_args_list
    ] == [2, 2, 1]
    # One call, shortest texts first, so batches need little padding.
    (texts,) = mock_settings.embed_model.get_text_embedding_batch.call_args.args
    assert texts == ["x", "xx", "xxx", "xxxx", "xxxxx"]


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_qdrant_similarity_search(
    mock_settings: MagicMock, mock_qdrant_client_cls: MagicMock
) -> None:
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client

    mock_settings.embed_model.get_query_embedding.return_value = [0.1] * 768

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
    assert kwargs["query"] == [0.1] * 768
    mock_settings.embed_model.get_query_embedding.assert_called_once_with("query")
    mock_settings.embed_model.get_text_embedding.assert_not_called()
    session_condition = kwargs["query_filter"].must[0]
    assert session_condition.match.value == "test_session"


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
def test_qdrant_delete_session(mock_qdrant_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client

    repo = QdrantRepository(collection_name="test_collection", vector_size=768)
    repo.delete_session("test_session")

    chunks, previews = mock_client.delete.call_args_list
    assert chunks.kwargs["collection_name"] == "test_collection"
    assert previews.kwargs["collection_name"] == "test_collection_images"


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
def test_qdrant_delete_document_scopes_session_and_filename(
    mock_qdrant_client_cls: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client
    repo = QdrantRepository(collection_name="test_collection", vector_size=768)

    repo.delete_document("session-one", "guide.pdf")

    selector = mock_client.delete.call_args_list[0].kwargs["points_selector"]
    assert len(selector.filter.must) == 2


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_empty_file_filter_returns_no_results_without_embedding(
    mock_settings: MagicMock, mock_qdrant_client_cls: MagicMock
) -> None:
    repo = QdrantRepository(collection_name="test_collection", vector_size=768)
    assert repo.similarity_search("query", file_filter=[]) == []
    mock_settings.embed_model.get_query_embedding.assert_not_called()


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
    client.scroll.side_effect = [([source_point], 77), ([], None), ([], None)]
    repo = QdrantRepository(collection_name="test", vector_size=2)

    assert repo.copy_document("old", "new", "guide.pdf") == 1

    copied = client.upsert.call_args_list[0].kwargs["points"][0]
    assert copied.id != source_point.id
    assert copied.vector == source_point.vector
    assert copied.payload == {**source_point.payload, "session_id": "new"}
    assert client.scroll.call_args_list[1].kwargs["offset"] == 77
    assert client.upsert.call_args_list[0].kwargs["wait"] is True
    mock_settings.embed_model.get_text_embedding_batch.assert_not_called()


def test_documents_are_found_by_content_digest_within_a_session() -> None:
    """The real local engine filters on session and content digest."""
    client = QdrantClient(location=":memory:")
    client.create_collection(
        collection_name="digest_test",
        vectors_config=qmodels.VectorParams(size=2, distance=qmodels.Distance.COSINE),
    )
    client.upsert(
        collection_name="digest_test",
        points=[
            qmodels.PointStruct(
                id=1,
                vector=[0.2, 0.8],
                payload={
                    "session_id": "s1",
                    "filename": "report.pdf",
                    "content_sha256": "abc",
                    "text": "evidence",
                },
            )
        ],
    )
    repo = object.__new__(QdrantRepository)
    repo.client = client
    repo.collection_name = "digest_test"

    assert repo.find_document_by_content("s1", "abc") == "report.pdf"
    assert repo.find_document_by_content("s2", "abc") is None
    assert repo.find_document_by_content("s1", "other") is None


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
    repo._ensure_image_collection()
    repo.save_images("source", "guide.pdf", {2: b"picture"})

    assert repo.copy_document("source", "target", "guide.pdf") == 1
    assert repo.get_image("target", "guide.pdf", 2) == b"picture"
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

    repo.delete_session("source")
    assert repo.get_session_files("source") == []
    assert repo.get_session_files("target") == ["guide.pdf"]


def _image_repository() -> QdrantRepository:
    """A repository on Qdrant's local engine with only the preview collection."""
    repo = object.__new__(QdrantRepository)
    repo.client = QdrantClient(location=":memory:")
    repo.collection_name = "previews"
    repo._ensure_image_collection()
    return repo


def test_image_previews_are_scoped_to_session_and_document() -> None:
    repo = _image_repository()
    repo.save_images("s1", "report.docx", {1: b"one", 2: b"two"})
    repo.save_images("s1", "report.docx", {2: b"two again"})

    assert repo.get_image("s1", "report.docx", 1) == b"one"
    assert repo.get_image("s1", "report.docx", 2) == b"two again"
    assert repo.get_image("s2", "report.docx", 1) is None
    assert repo.get_image("s1", "other.docx", 1) is None
    assert repo.get_image("s1", "report.docx", 3) is None


def test_deleting_a_document_or_session_deletes_its_previews() -> None:
    repo = _image_repository()
    repo.collection_name = "previews"
    repo.client.create_collection(
        collection_name="previews",
        vectors_config=qmodels.VectorParams(size=2, distance=qmodels.Distance.COSINE),
    )
    repo._keywords.invalidate("s1")
    repo.save_images("s1", "a.docx", {1: b"a"})
    repo.save_images("s1", "b.docx", {1: b"b"})
    repo.save_images("s2", "a.docx", {1: b"other session"})

    repo.delete_document("s1", "a.docx")
    assert repo.get_image("s1", "a.docx", 1) is None
    assert repo.get_image("s1", "b.docx", 1) == b"b"

    repo.delete_session("s1")
    assert repo.get_image("s1", "b.docx", 1) is None
    assert repo.get_image("s2", "a.docx", 1) == b"other session"


def test_embedded_texts_keep_their_order() -> None:
    """Sorting by length for batching never mixes up which vector is whose."""
    from backend.infrastructure.database.qdrant_repo import embed_texts

    with patch("backend.infrastructure.database.qdrant_repo.Settings") as settings:
        settings.embed_model.get_text_embedding_batch.side_effect = lambda texts: [
            [float(len(text))] for text in texts
        ]
        assert embed_texts(["ccc", "a", "bb", ""]) == [[3.0], [1.0], [2.0], [0.0]]
