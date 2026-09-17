from unittest.mock import MagicMock, patch

import pytest

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
