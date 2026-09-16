"""Automated tests for frontend client, mode parsing, and citation formatting."""

from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from frontend.client import (
    MAX_FILE_SIZE_BYTES,
    ParsRAGClient,
    format_citation,
    parse_mode,
)


def test_health_endpoint() -> None:
    """Tests the /health endpoint in FastAPI."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_parse_mode() -> None:
    """Verifies UI label normalization to backend QueryMode values."""
    assert parse_mode("Strict RAG") == "strict"
    assert parse_mode("Strict RAG (فقط اسناد)") == "strict"
    assert parse_mode("strict") == "strict"
    assert parse_mode("Hybrid RAG") == "hybrid"
    assert parse_mode("Hybrid RAG (ترکیبی)") == "hybrid"
    assert parse_mode("hybrid") == "hybrid"
    assert parse_mode("LLM Only") == "llm-only"
    assert parse_mode("LLM Only (فقط مدل)") == "llm-only"
    assert parse_mode("llm-only") == "llm-only"
    # Fallback to default hybrid
    assert parse_mode("unknown_mode") == "hybrid"


def test_format_citation_with_score() -> None:
    """Verifies citation formatting when score and metadata are present."""
    node: dict[str, Any] = {
        "text": "این یک متن آزمایشی است.",
        "metadata": {"filename": "test_doc.docx"},
        "score": 0.8923,
    }
    title, body = format_citation(node, index=1)
    assert "📄 منبع 1: test_doc.docx" in title
    assert "`test_doc.docx`" in body
    assert "0.892" in body
    assert "این یک متن آزمایشی است." in body


def test_format_citation_without_score() -> None:
    """Verifies citation formatting when score or metadata is absent."""
    node: dict[str, Any] = {
        "text": "نمونه بدون امتیاز",
    }
    title, body = format_citation(node, index=2)
    assert "📄 منبع 2: سند نامشخص" in title
    assert "بدون امتیاز عددی" in body
    assert "نمونه بدون امتیاز" in body


@pytest.mark.asyncio
async def test_client_ingest_validation_errors() -> None:
    """Verifies that client catches client-side validation errors before sending."""
    frontend_client = ParsRAGClient(base_url="http://localhost:8000")

    # Empty files list
    with pytest.raises(ValueError, match="هیچ فایلی برای بارگذاری"):
        await frontend_client.ingest_files([])

    # More than 5 files
    too_many = [(f"doc_{i}.docx", b"dummy") for i in range(6)]
    with pytest.raises(ValueError, match="حداکثر 5 فایل"):
        await frontend_client.ingest_files(too_many)

    # Unsupported file extension
    with pytest.raises(ValueError, match="پشتیبانی نمی‌شود"):
        await frontend_client.ingest_files([("malicious.exe", b"bytes")])

    # File exceeding 50MB
    oversized = [("big.pdf", b"x" * (MAX_FILE_SIZE_BYTES + 10))]
    with pytest.raises(ValueError, match="بیشتر است"):
        await frontend_client.ingest_files(oversized)


@pytest.mark.asyncio
async def test_client_ingest_mocked_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests client ingest_files method with mocked httpx response."""
    frontend_client = ParsRAGClient(base_url="http://localhost:8000")

    class MockResponse:
        status_code = 200

        def json(self) -> dict[str, str]:
            return {"message": "Successfully ingested 1 file(s)"}

    async def mock_post(self: Any, url: str, **kwargs: Any) -> MockResponse:
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    res = await frontend_client.ingest_files(
        [("sample.docx", b"mock content")], session_id="test_session"
    )
    assert res == {"message": "Successfully ingested 1 file(s)"}


@pytest.mark.asyncio
async def test_client_query_mocked_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests client query method with mocked httpx response."""
    frontend_client = ParsRAGClient(base_url="http://localhost:8000")

    class MockResponse:
        status_code = 200

        def json(self) -> dict[str, Any]:
            return {
                "answer": "پاسخ مدل هوشمند",
                "source_nodes": [
                    {
                        "text": "متن شاهد",
                        "metadata": {"filename": "guide.pdf"},
                        "score": 0.95,
                    }
                ],
            }

    async def mock_post(self: Any, url: str, **kwargs: Any) -> MockResponse:
        assert kwargs["json"]["prompt"] == "پرسش کاربر"
        assert kwargs["json"]["mode"] == "strict"
        assert kwargs["json"]["session_id"] == "test_session_1"
        assert kwargs["json"]["top_k"] == 20
        return MockResponse()

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await frontend_client.query(
        prompt="پرسش کاربر",
        mode="Strict RAG",
        session_id="test_session_1",
        top_k=20,
    )
    assert result["answer"] == "پاسخ مدل هوشمند"
    assert len(result["source_nodes"]) == 1
    assert result["source_nodes"][0]["metadata"]["filename"] == "guide.pdf"
