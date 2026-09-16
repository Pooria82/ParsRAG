from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.api.dependencies import get_document_repository
from backend.core.models.domain import ExtractedNode, QueryResponse
from backend.infrastructure.parsers.document_parser import EmptyDocumentError
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_ingest_success() -> None:
    mock_repo = MagicMock()
    app.dependency_overrides[get_document_repository] = lambda: mock_repo

    with (
        patch("backend.api.routes.parse_document") as mock_parse_document,
        patch("backend.api.routes.chunk_text") as mock_chunk_text,
    ):
        mock_parse_document.return_value = "Extracted text"
        mock_chunk_text.return_value = [
            ExtractedNode(text="Extracted text", metadata={"filename": "test.pdf"})
        ]

        response = client.post(
            "/ingest",
            files={"file": ("test.pdf", b"fake pdf bytes", "application/pdf")},
            data={"session_id": "session-123"},
        )

        assert response.status_code == 200
        assert "Successfully ingested test.pdf" in response.json()["message"]

        mock_parse_document.assert_called_once()
        mock_chunk_text.assert_called_once()
        mock_repo.save_nodes.assert_called_once()

    app.dependency_overrides.clear()


def test_ingest_empty_document() -> None:
    mock_repo = MagicMock()
    app.dependency_overrides[get_document_repository] = lambda: mock_repo

    with patch("backend.api.routes.parse_document") as mock_parse_document:
        mock_parse_document.side_effect = EmptyDocumentError("No text found")

        response = client.post(
            "/ingest", files={"file": ("empty.pdf", b"empty bytes", "application/pdf")}
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "No text found"

    app.dependency_overrides.clear()


@patch("backend.api.routes.CondenseQuestionPipeline")
@patch("backend.api.routes.get_query_strategy")
def test_query_success(
    mock_get_strategy: MagicMock, mock_condenser_cls: MagicMock
) -> None:
    mock_condenser = MagicMock()
    mock_condenser.condense.return_value = "condensed query"
    mock_condenser_cls.return_value = mock_condenser

    mock_strategy = MagicMock()
    mock_strategy.execute.return_value = QueryResponse(
        answer="This is the answer", source_nodes=[]
    )
    mock_get_strategy.return_value = mock_strategy

    payload = {"prompt": "What is this?", "mode": "hybrid"}

    response = client.post("/query", json=payload)

    assert response.status_code == 200
    assert response.json()["answer"] == "This is the answer"
    mock_condenser.condense.assert_called_once_with("What is this?", [])
    mock_strategy.execute.assert_called_once_with(
        query="condensed query",
        chat_history=[],
        session_id=None,
        top_k=None,
        file_filter=None,
    )


@patch("backend.api.routes.CondenseQuestionPipeline")
@patch("backend.api.routes.get_query_strategy")
def test_query_with_custom_top_k(
    mock_get_strategy: MagicMock, mock_condenser_cls: MagicMock
) -> None:
    mock_condenser = MagicMock()
    mock_condenser.condense.return_value = "condensed query"
    mock_condenser_cls.return_value = mock_condenser

    mock_strategy = MagicMock()
    mock_strategy.execute.return_value = QueryResponse(
        answer="Custom top_k answer", source_nodes=[]
    )
    mock_get_strategy.return_value = mock_strategy

    payload = {"prompt": "Aggregate all sections", "mode": "strict", "top_k": 20}

    response = client.post("/query", json=payload)

    assert response.status_code == 200
    assert response.json()["answer"] == "Custom top_k answer"
    mock_strategy.execute.assert_called_once_with(
        query="condensed query",
        chat_history=[],
        session_id=None,
        top_k=20,
        file_filter=None,
    )


@patch("backend.api.routes.CondenseQuestionPipeline")
def test_global_exception_handler(mock_condenser_cls: MagicMock) -> None:
    """Test that unexpected exceptions do not leak stack traces."""
    mock_condenser = MagicMock()
    mock_condenser.condense.side_effect = Exception(
        "Super secret database failure at line 42"
    )
    mock_condenser_cls.return_value = mock_condenser

    payload = {"prompt": "Trigger crash", "mode": "strict"}

    response = client.post("/query", json=payload)

    assert response.status_code == 500
    # Ensure the secret error message is NOT in the response
    assert "Super secret database failure" not in response.text
    assert response.json()["detail"] == "An internal server error occurred."


def test_get_session_files_success() -> None:
    mock_repo = MagicMock()
    mock_repo.get_session_files.return_value = ["file1.pdf", "file2.docx"]
    app.dependency_overrides[get_document_repository] = lambda: mock_repo

    response = client.get("/sessions/test-session-123/files")
    assert response.status_code == 200
    assert response.json() == ["file1.pdf", "file2.docx"]
    mock_repo.get_session_files.assert_called_once_with("test-session-123")

    app.dependency_overrides.clear()


def test_delete_session_success() -> None:
    mock_repo = MagicMock()
    app.dependency_overrides[get_document_repository] = lambda: mock_repo

    response = client.delete("/sessions/test-session-123")
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]
    mock_repo.delete_session.assert_called_once_with("test-session-123")

    app.dependency_overrides.clear()


def test_session_endpoints_invalid_session_id() -> None:
    response_get = client.get("/sessions/invalid session with spaces/files")
    assert response_get.status_code == 400
    assert "Invalid session_id" in response_get.json()["detail"]

    response_delete = client.delete("/sessions/invalid;semicolon")
    assert response_delete.status_code == 400
    assert "Invalid session_id" in response_delete.json()["detail"]
