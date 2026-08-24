from unittest.mock import MagicMock, patch

from backend.core.models.domain import ExtractedNode
from backend.infrastructure.database.qdrant_repo import QdrantRepository


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_qdrant_save_nodes(mock_settings, mock_qdrant_client_cls):
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client

    # Mock embeddings
    mock_settings.embed_model.get_text_embedding_batch.return_value = [
        [0.1] * 768,
        [0.2] * 768,
    ]

    repo = QdrantRepository(collection_name="test_collection")

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

@patch('backend.infrastructure.database.qdrant_repo.QdrantClient')
@patch('backend.infrastructure.database.qdrant_repo.Settings')
def test_qdrant_similarity_search(mock_settings, mock_qdrant_client_cls) -> None:
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client
    
    mock_settings.embed_model.get_text_embedding.return_value = [0.1] * 768
    
    mock_point = MagicMock()
    mock_point.payload = {'text': 'Found text', 'page': 1}
    mock_point.score = 0.95
    
    mock_query_result = MagicMock()
    mock_query_result.points = [mock_point]
    mock_client.query_points.return_value = mock_query_result
    
    repo = QdrantRepository(collection_name='test_collection')
    results = repo.similarity_search('query', top_k=1, session_id='test_session')
    
    assert len(results) == 1
    assert results[0].text == 'Found text'
    assert results[0].score == 0.95
    assert results[0].metadata == {'page': 1}
    
    mock_client.query_points.assert_called_once()
    _, kwargs = mock_client.query_points.call_args
    assert kwargs['collection_name'] == 'test_collection'
    assert kwargs['limit'] == 1


@patch('backend.infrastructure.database.qdrant_repo.QdrantClient')
def test_qdrant_delete_session(mock_qdrant_client_cls) -> None:
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client
    
    repo = QdrantRepository(collection_name='test_collection')
    repo.delete_session('test_session')
    
    mock_client.delete.assert_called_once()
    _, kwargs = mock_client.delete.call_args
    assert kwargs['collection_name'] == 'test_collection'

