import asyncio
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_document_repository
from backend.core.models.domain import QueryResponse
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def override_repo() -> Generator[MagicMock, None, None]:
    mock_repo = MagicMock()
    app.dependency_overrides[get_document_repository] = lambda: mock_repo
    yield mock_repo
    app.dependency_overrides.clear()


# ==============================================================================
# Task 6.2.3: Malformed Payloads Tests
# ==============================================================================


def test_ingest_unsupported_file_extension() -> None:
    """Ensure unsupported file formats are rejected with HTTP 400."""
    response = client.post(
        "/ingest",
        files={
            "file": ("malicious.exe", b"binary content", "application/x-msdownload")
        },
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_ingest_oversized_file() -> None:
    """Ensure files exceeding 50MB are rejected with HTTP 413."""
    # Create fake oversized bytes (51 MB)
    mock_file = MagicMock()
    mock_file.filename = "large.docx"
    mock_file.file.read.return_value = b"0" * (51 * 1024 * 1024)

    with patch("fastapi.UploadFile", return_value=mock_file):
        response = client.post(
            "/ingest",
            files={
                "file": (
                    "large.docx",
                    b"0" * 100,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    # Testing standard client with oversized bytes directly
    oversized_bytes = b"0" * (51 * 1024 * 1024)
    response = client.post(
        "/ingest",
        files={"file": ("oversized.docx", oversized_bytes, "application/octet-stream")},
    )
    assert response.status_code == 413
    assert "exceeds the 50MB limit" in response.json()["detail"]


def test_ingest_corrupted_document() -> None:
    """Ensure corrupted docx/pptx bytes fail gracefully with HTTP 400."""
    response = client.post(
        "/ingest",
        files={
            "file": (
                "corrupted.docx",
                b"random garbage not a zip or docx",
                "application/octet-stream",
            )
        },
    )
    assert response.status_code == 400


# ==============================================================================
# Task 6.4.1: Zero-Leakage Audit Tests
# ==============================================================================


@patch("backend.api.routes.CondenseQuestionPipeline")
def test_zero_leakage_on_key_error(mock_condenser_cls: MagicMock) -> None:
    """Ensure internal KeyErrors return sterile HTTP 500 without leaking stack traces."""
    mock_condenser = MagicMock()
    mock_condenser.condense.side_effect = KeyError("internal_database_secret_key_id")
    mock_condenser_cls.return_value = mock_condenser

    payload = {"prompt": "trigger", "mode": "strict"}
    response = client.post("/query", json=payload)

    assert response.status_code == 500
    assert "internal_database_secret_key_id" not in response.text
    assert "KeyError" not in response.text
    assert "Traceback" not in response.text
    assert response.json()["detail"] == "An internal server error occurred."


@patch("backend.api.routes.CondenseQuestionPipeline")
def test_zero_leakage_on_zero_division(mock_condenser_cls: MagicMock) -> None:
    """Ensure division by zero returns sterile HTTP 500 without stack trace leaks."""
    mock_condenser = MagicMock()
    mock_condenser.condense.side_effect = ZeroDivisionError(
        "division by zero at math_utils.py:108"
    )
    mock_condenser_cls.return_value = mock_condenser

    payload = {"prompt": "trigger", "mode": "hybrid"}
    response = client.post("/query", json=payload)

    assert response.status_code == 500
    assert "math_utils.py" not in response.text
    assert "ZeroDivisionError" not in response.text
    assert response.json()["detail"] == "An internal server error occurred."


# ==============================================================================
# Task 6.4.2: Input Sanitization Tests (Path Traversal, Injection, XSS)
# ==============================================================================


@pytest.mark.parametrize(
    "malicious_session",
    [
        "../../etc/passwd",
        "..\\..\\Windows\\System32",
        "<script>alert('xss')</script>",
        "admin' OR 1=1 --",
        '{"$gt": ""}',
        "a" * 65,  # Exceeds 64 chars
        "session; DROP TABLE users;",
        "invalid session with spaces",
    ],
)
def test_query_session_id_sanitization(malicious_session: str) -> None:
    """Ensure malicious session_ids in /query are rejected by Pydantic V2 (HTTP 422)."""
    payload = {
        "prompt": "Test query",
        "mode": "strict",
        "session_id": malicious_session,
    }
    response = client.post("/query", json=payload)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "malicious_session",
    [
        "../../etc/passwd",
        "..\\..\\Windows\\System32",
        "<script>alert('xss')</script>",
        "admin' OR 1=1 --",
        "a" * 65,
    ],
)
def test_ingest_session_id_sanitization(malicious_session: str) -> None:
    """Ensure malicious session_ids in /ingest are rejected with HTTP 400."""
    response = client.post(
        "/ingest",
        files={"file": ("test.docx", b"sample", "application/octet-stream")},
        data={"session_id": malicious_session},
    )
    assert response.status_code == 400
    assert "Invalid session_id format" in response.json()["detail"]


# ==============================================================================
# Task 6.4.3: Concurrency Test (10 Simultaneous Async Requests)
# ==============================================================================


@pytest.mark.anyio
@patch("backend.api.routes.CondenseQuestionPipeline")
@patch("backend.api.routes.get_query_strategy")
async def test_concurrent_queries_no_race_condition(
    mock_get_strategy: MagicMock,
    mock_condenser_cls: MagicMock,
) -> None:
    """Send 10 simultaneous asynchronous requests to /query and assert all succeed."""
    mock_condenser = MagicMock()
    mock_condenser.condense.side_effect = lambda q, h: f"condensed_{q}"
    mock_condenser_cls.return_value = mock_condenser

    mock_strategy = MagicMock()
    mock_strategy.execute.side_effect = lambda query, chat_history, session_id: (
        QueryResponse(answer=f"Answer for {query}", source_nodes=[])
    )
    mock_get_strategy.return_value = mock_strategy

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        tasks = [
            ac.post(
                "/query",
                json={
                    "prompt": f"Concurrent Question #{i}",
                    "mode": "hybrid",
                    "session_id": f"session-{i}",
                },
            )
            for i in range(10)
        ]

        responses = await asyncio.gather(*tasks)

    for i, res in enumerate(responses):
        assert res.status_code == 200
        data = res.json()
        assert data["answer"] == f"Answer for condensed_Concurrent Question #{i}"
