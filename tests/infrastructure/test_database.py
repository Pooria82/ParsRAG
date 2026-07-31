import pytest
from unittest.mock import MagicMock, patch
from backend.infrastructure.database.qdrant_repo import QdrantRepository
from backend.core.models.domain import ExtractedNode

@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_qdrant_save_nodes(mock_settings, mock_qdrant_client_cls):
    mock_client = MagicMock()
    mock_qdrant_client_cls.return_value = mock_client
    
    # Mock embeddings
    mock_settings.embed_model.get_text_embedding_batch.return_value = [[0.1]*768, [0.2]*768]
    
    repo = QdrantRepository(collection_name="test_collection")
    
    nodes = [
        ExtractedNode(text="Chunk 1", metadata={"page": 1}),
        ExtractedNode(text="Chunk 2", metadata={"page": 2})
    ]
    
    repo.save_nodes(nodes, session_id="test_session")
    
    # Assert client.upsert was called
    mock_client.upsert.assert_called_once()
    args, kwargs = mock_client.upsert.call_args
    assert kwargs["collection_name"] == "test_collection"
    assert len(kwargs["points"]) == 2
    assert kwargs["points"][0].payload["session_id"] == "test_session"
    assert kwargs["points"][0].payload["text"] == "Chunk 1"
