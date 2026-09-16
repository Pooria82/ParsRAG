"""Unit and resilience tests for database and domain error handling."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from qdrant_client.http.exceptions import ResponseHandlingException

from backend.api.dependencies import get_document_repository
from backend.core.exceptions import (
    VectorDBConnectionError,
)
from backend.core.models.domain import ExtractedNode
from backend.infrastructure.database.qdrant_repo import QdrantRepository
from backend.main import app


def test_qdrant_initialization_failure_raises_vectordb_error() -> None:
    """Tests that network or initialization errors in QdrantRepository raise VectorDBConnectionError."""
    with patch(
        "backend.infrastructure.database.qdrant_repo.QdrantClient"
    ) as mock_client_cls:
        mock_client = MagicMock()
        mock_client.collection_exists.side_effect = ResponseHandlingException(
            Exception("Connection refused")
        )
        mock_client_cls.return_value = mock_client

        try:
            QdrantRepository(host="invalid-host", port=9999)
            assert False, "Expected VectorDBConnectionError was not raised"
        except VectorDBConnectionError as exc:
            assert "Failed to connect to or initialize Qdrant" in str(exc)


def test_qdrant_save_nodes_failure_raises_vectordb_error() -> None:
    """Tests that upsert failures in QdrantRepository raise VectorDBConnectionError."""
    with (
        patch(
            "backend.infrastructure.database.qdrant_repo.QdrantClient"
        ) as mock_client_cls,
        patch("backend.infrastructure.database.qdrant_repo.Settings") as mock_settings,
    ):
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_client.upsert.side_effect = Exception("Write timeout")
        mock_client_cls.return_value = mock_client
        mock_settings.embed_model.get_text_embedding_batch.return_value = [[0.1] * 768]

        repo = QdrantRepository(collection_name="test_col")
        node = ExtractedNode(text="متن تستی", metadata={})

        try:
            repo.save_nodes([node])
            assert False, "Expected VectorDBConnectionError was not raised"
        except VectorDBConnectionError as exc:
            assert "Failed to save nodes in Qdrant" in str(exc)


def test_qdrant_similarity_search_failure_raises_vectordb_error() -> None:
    """Tests that query failures in QdrantRepository raise VectorDBConnectionError."""
    with (
        patch(
            "backend.infrastructure.database.qdrant_repo.QdrantClient"
        ) as mock_client_cls,
        patch("backend.infrastructure.database.qdrant_repo.Settings") as mock_settings,
    ):
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = True
        mock_client.query_points.side_effect = Exception("Search connection dropped")
        mock_client_cls.return_value = mock_client
        mock_settings.embed_model.get_text_embedding.return_value = [0.1] * 768

        repo = QdrantRepository(collection_name="test_col")

        try:
            repo.similarity_search("پرسش تستی")
            assert False, "Expected VectorDBConnectionError was not raised"
        except VectorDBConnectionError as exc:
            assert "Failed to perform similarity search in Qdrant" in str(exc)


def test_parsrag_domain_exception_handler_sterile_response() -> None:
    """Tests that domain-level ParsRAG exceptions return a sterile HTTP 500 response."""
    mock_repo = MagicMock(spec=QdrantRepository)
    mock_repo.similarity_search.side_effect = VectorDBConnectionError(
        "Internal DB Credentials/Secret at 10.0.0.1"
    )

    app.dependency_overrides[get_document_repository] = lambda: mock_repo
    client = TestClient(app, raise_server_exceptions=False)

    try:
        response = client.post(
            "/query",
            json={"prompt": "تست خطا", "mode": "strict"},
        )
        assert response.status_code == 500
        # Verify zero leak of internal secrets or python tracebacks
        assert "Internal DB Credentials" not in response.text
        assert "Traceback" not in response.text
        assert "10.0.0.1" not in response.text
        json_resp = response.json()
        assert "detail" in json_resp
    finally:
        app.dependency_overrides.clear()
