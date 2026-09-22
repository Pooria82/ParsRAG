from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.api.dependencies import get_document_repository
from backend.core.models.domain import ExtractedNode, QueryResponse
from backend.core.runtime import runtime_state
from backend.infrastructure.parsers.document_parser import EmptyDocumentError
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


@patch("backend.api.dependencies._shared_document_repository")
def test_health_endpoints_separate_liveness_and_readiness(
    mock_repository: MagicMock,
) -> None:
    """Liveness stays available while readiness verifies the vector store."""
    runtime_state.mark_failed()
    assert client.get("/health/live").status_code == 200
    preparing = client.get("/health/ready")
    assert preparing.status_code == 503
    assert preparing.json() == {"status": "failed"}

    runtime_state.mark_ready()
    mock_repository.return_value.is_ready.return_value = True
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ready"}
    assert len(ready.headers["x-correlation-id"]) == 36


def test_capabilities_expose_server_side_upload_contract() -> None:
    """The frontend can discover limits and formats from the running backend."""
    response = client.get("/capabilities")

    assert response.status_code == 200
    payload = response.json()["ingestion"]
    assert payload["max_files_per_session"] == 10
    assert payload["max_file_size_bytes"] == 100 * 1024 * 1024
    assert ".json" in payload["supported_extensions"]
    assert ".png" in payload["supported_extensions"]


def test_ingest_success() -> None:
    mock_repo = MagicMock()
    app.dependency_overrides[get_document_repository] = lambda: mock_repo

    with (
        patch("backend.api.routes._validate_file"),
        patch("backend.api.routes.parse_document_sections") as mock_parse_document,
        patch("backend.api.routes.chunk_text") as mock_chunk_text,
    ):
        mock_parse_document.return_value = [
            MagicMock(text="Extracted text", metadata={"page": 1})
        ]
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

    with (
        patch("backend.api.routes._validate_file"),
        patch("backend.api.routes.parse_document_sections") as mock_parse_document,
    ):
        mock_parse_document.side_effect = EmptyDocumentError("No text found")

        response = client.post(
            "/ingest",
            files={"file": ("empty.pdf", b"empty bytes", "application/pdf")},
            data={"session_id": "session-123"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "No text found"

    app.dependency_overrides.clear()


def test_ingest_requires_session_boundary() -> None:
    """Documents cannot be stored in an implicit shared namespace."""
    response = client.post(
        "/ingest", files={"file": ("test.pdf", b"fake pdf bytes", "application/pdf")}
    )

    assert response.status_code == 422


def test_document_query_requires_session_boundary() -> None:
    """Document-backed modes reject queries without a session identifier."""
    response = client.post("/query", json={"prompt": "Question", "mode": "strict"})

    assert response.status_code == 422


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

    payload = {"prompt": "What is this?", "mode": "hybrid", "session_id": "session-123"}

    response = client.post("/query", json=payload)

    assert response.status_code == 200
    assert response.json()["answer"] == "This is the answer"
    mock_condenser.condense.assert_called_once_with("What is this?", [])
    mock_strategy.execute.assert_called_once_with(
        query="condensed query",
        chat_history=[],
        session_id="session-123",
        top_k=None,
        file_filter=None,
    )


@patch("backend.api.routes.CondenseQuestionPipeline")
@patch("backend.api.routes.get_query_strategy")
def test_query_exposes_non_sensitive_progress(
    mock_get_strategy: MagicMock, mock_condenser_cls: MagicMock
) -> None:
    """A caller-supplied opaque ID exposes stages without query content."""
    request_id = "4df43765-52bf-4d3e-b8df-530596aacd84"
    mock_condenser_cls.return_value.condense.return_value = "condensed query"

    def execute_with_progress(**kwargs: object) -> QueryResponse:
        progress = kwargs["progress"]
        assert callable(progress)
        progress("retrieving")
        progress("generating")
        return QueryResponse(answer="Answer", source_nodes=[])

    mock_get_strategy.return_value.execute.side_effect = execute_with_progress
    response = client.post(
        "/query",
        json={
            "prompt": "Question",
            "mode": "hybrid",
            "session_id": "session-123",
            "request_id": request_id,
        },
    )

    assert response.status_code == 200
    progress_response = client.get(f"/queries/{request_id}/progress")
    assert progress_response.status_code == 200
    assert progress_response.json() == {"stage": "complete"}
    assert "Question" not in progress_response.text


def test_unknown_query_progress_is_not_found() -> None:
    """Unknown progress identifiers do not create registry entries."""
    response = client.get("/queries/4df43765-52bf-4d3e-b8df-530596aacd85/progress")

    assert response.status_code == 404


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

    payload = {
        "prompt": "Aggregate all sections",
        "mode": "strict",
        "top_k": 20,
        "session_id": "session-123",
    }

    response = client.post("/query", json=payload)

    assert response.status_code == 200
    assert response.json()["answer"] == "Custom top_k answer"
    mock_strategy.execute.assert_called_once_with(
        query="condensed query",
        chat_history=[],
        session_id="session-123",
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

    payload = {"prompt": "Trigger crash", "mode": "strict", "session_id": "session-123"}

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


def test_delete_one_session_document() -> None:
    mock_repo = MagicMock()
    app.dependency_overrides[get_document_repository] = lambda: mock_repo
    response = client.request(
        "DELETE", "/sessions/test-session-123/files", json={"filename": "راهنما.pdf"}
    )
    assert response.status_code == 200
    mock_repo.delete_document.assert_called_once_with("test-session-123", "راهنما.pdf")
    app.dependency_overrides.clear()


def test_session_endpoints_invalid_session_id() -> None:
    response_get = client.get("/sessions/invalid session with spaces/files")
    assert response_get.status_code == 400
    assert "Invalid session_id" in response_get.json()["detail"]

    response_delete = client.delete("/sessions/invalid;semicolon")
    assert response_delete.status_code == 400
    assert "Invalid session_id" in response_delete.json()["detail"]


@patch("backend.api.routes.get_model_configuration")
def test_model_configuration_never_returns_api_key(mock_get: MagicMock) -> None:
    from backend.core.models.domain import ModelConfigurationResponse, ModelProvider

    mock_get.return_value = ModelConfigurationResponse(
        provider=ModelProvider.API,
        model_name="google/gemma-4-26b-a4b-it",
        base_url="https://openrouter.ai/api/v1",
        api_key_configured=True,
    )
    response = client.get("/models/configuration")
    assert response.status_code == 200
    assert response.json()["model_name"] == "google/gemma-4-26b-a4b-it"
    assert "api_key" not in response.json()


@patch("backend.api.routes.configure_model")
def test_update_model_configuration(mock_configure: MagicMock) -> None:
    from backend.core.models.domain import ModelConfigurationResponse, ModelProvider

    mock_configure.return_value = ModelConfigurationResponse(
        provider=ModelProvider.OLLAMA,
        model_name="gemma3:12b",
        base_url="http://localhost:11434",
        api_key_configured=False,
    )
    response = client.put(
        "/models/configuration",
        json={
            "provider": "ollama",
            "model_name": "gemma3:12b",
            "base_url": "http://localhost:11434",
        },
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "ollama"


@patch("backend.api.routes.generate_conversation_title")
def test_generate_conversation_title(mock_generate: MagicMock) -> None:
    """The title endpoint validates input and returns only the generated label."""
    runtime_state.mark_ready()
    mock_generate.return_value = "ساختار رمزنگاری فیستل"

    response = client.post(
        "/conversations/title",
        json={"prompt": "ساختار فیستل چیست؟", "language": "fa"},
    )

    assert response.status_code == 200
    assert response.json() == {"title": "ساختار رمزنگاری فیستل"}
    mock_generate.assert_called_once_with("ساختار فیستل چیست؟", "fa")
