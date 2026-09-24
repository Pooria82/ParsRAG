from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.api.dependencies import get_document_repository
from backend.core.models.domain import ExtractedNode, QueryResponse
from backend.core.strategies.multi_doc_utils import (
    format_multi_doc_context,
    parse_tagged_segments,
    resolve_target_files,
)
from backend.core.strategies.strict_rag import StrictRAGStrategy
from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_tagged_prompt_keeps_each_question_with_its_document() -> None:
    prompt = "مقایسه کن: @{الف.pdf} هزینه چقدر است؟ @{ب.pdf} زمان چقدر است؟"
    assert parse_tagged_segments(prompt, ["الف.pdf", "ب.pdf"]) == [
        ("الف.pdf", "مقایسه کن: هزینه چقدر است"),
        ("ب.pdf", "زمان چقدر است؟"),
    ]
    assert parse_tagged_segments(
        "در @{الف.pdf} هزینه را بگو و در @{ب.pdf} زمان را بگو",
        ["الف.pdf", "ب.pdf"],
    ) == [
        ("الف.pdf", "در هزینه را بگو"),
        ("ب.pdf", "در زمان را بگو"),
    ]
    assert parse_tagged_segments(
        r"@{گزارش \{نهایی\}.pdf} بودجه را بگو", ["گزارش {نهایی}.pdf"]
    ) == [("گزارش {نهایی}.pdf", "بودجه را بگو")]
    with pytest.raises(ValueError, match="not indexed"):
        parse_tagged_segments("@{secret.pdf} متن", ["الف.pdf"])
    with pytest.raises(ValueError, match="malformed"):
        parse_tagged_segments("@{الف.pdf متن", ["الف.pdf"])
    with pytest.raises(ValueError, match="malformed"):
        parse_tagged_segments("@{الف.pdf} هزینه و @{ب.pdf زمان", ["الف.pdf", "ب.pdf"])
    with pytest.raises(ValueError, match="Too many"):
        parse_tagged_segments(" ".join(["@{الف.pdf} سوال"] * 21), ["الف.pdf"])


def test_multi_file_ingest_success() -> None:
    """Verifies that uploading multiple files in a single batch succeeds."""
    mock_repo = MagicMock()
    app.dependency_overrides[get_document_repository] = lambda: mock_repo

    with (
        patch("backend.api.routes._validate_file"),
        patch("backend.api.routes.parse_document_sections") as mock_parse_document,
        patch("backend.api.routes.chunk_text") as mock_chunk_text,
    ):
        mock_parse_document.return_value = [
            MagicMock(text="Extracted text content", metadata={"section": 1})
        ]
        mock_chunk_text.return_value = [
            ExtractedNode(text="Chunk 1", metadata={"filename": "doc.docx"})
        ]

        files_payload = [
            (
                "files",
                (
                    "doc1.docx",
                    b"fake docx 1",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
            (
                "files",
                (
                    "doc2.docx",
                    b"fake docx 2",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
            (
                "files",
                (
                    "doc3.pptx",
                    b"fake pptx 3",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                ),
            ),
        ]

        response = client.post(
            "/ingest",
            files=files_payload,
            data={"session_id": "multi-session-1"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "Successfully ingested 3 file(s)" in data["message"]
        assert "doc1.docx" in data["message"]
        assert "doc2.docx" in data["message"]
        assert "doc3.pptx" in data["message"]

        assert mock_parse_document.call_count == 3
        assert mock_chunk_text.call_count == 3
        assert mock_repo.save_nodes.call_count == 3

    app.dependency_overrides.clear()


def test_reuse_document_copies_indexed_file_without_upload() -> None:
    repo = MagicMock()
    repo.get_session_files.side_effect = [["guide.pdf"], []]
    repo.copy_document.return_value = 4
    app.dependency_overrides[get_document_repository] = lambda: repo

    response = client.post(
        "/sessions/new/files/reuse",
        json={
            "source_session_id": "old",
            "filename": "guide.pdf",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"filename": "guide.pdf", "chunks": 4}
    repo.copy_document.assert_called_once_with("old", "new", "guide.pdf")
    app.dependency_overrides.clear()


def test_reuse_rejects_missing_or_duplicate_file() -> None:
    repo = MagicMock()
    app.dependency_overrides[get_document_repository] = lambda: repo
    repo.get_session_files.return_value = []
    missing = client.post(
        "/sessions/new/files/reuse",
        json={
            "source_session_id": "old",
            "filename": "guide.pdf",
        },
    )
    assert missing.status_code == 404
    repo.get_session_files.side_effect = [["guide.pdf"], ["guide.pdf"]]
    duplicate = client.post(
        "/sessions/new/files/reuse",
        json={
            "source_session_id": "old",
            "filename": "guide.pdf",
        },
    )
    assert duplicate.status_code == 409
    repo.copy_document.assert_not_called()
    app.dependency_overrides.clear()


def test_multi_file_ingest_exceeds_limit() -> None:
    """Verifies that uploading more than 10 files returns HTTP 400."""
    mock_repo = MagicMock()
    app.dependency_overrides[get_document_repository] = lambda: mock_repo

    files_payload = [
        (
            "files",
            (
                f"doc{i}.docx",
                b"bytes",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )
        for i in range(1, 12)
    ]

    response = client.post(
        "/ingest",
        files=files_payload,
        data={"session_id": "multi-session-overflow"},
    )

    assert response.status_code == 400
    assert (
        "A maximum of 10 files can be uploaded per request" in response.json()["detail"]
    )

    app.dependency_overrides.clear()


def test_ingest_enforces_capacity_across_separate_requests() -> None:
    """Existing session files count toward the ten-file capacity."""
    mock_repo = MagicMock()
    mock_repo.get_session_files.return_value = [
        f"existing-{index}.pdf" for index in range(10)
    ]
    app.dependency_overrides[get_document_repository] = lambda: mock_repo

    response = client.post(
        "/ingest",
        files={"file": ("extra.txt", b"content", "text/plain")},
        data={"session_id": "full-session"},
    )

    assert response.status_code == 400
    assert "at most 10 files" in response.json()["detail"]
    app.dependency_overrides.clear()


def test_resolve_target_files_logic() -> None:
    """Tests intelligent file targeting vs. cross-document broad intent."""
    available = ["گزارش اول.docx", "گزارش دوم_ فاز سوم.docx", "نیازمندی‌ها.docx"]

    # Explicit filter priority
    assert resolve_target_files(
        "هر سوالی", available, explicit_filter=["نیازمندی‌ها.docx"]
    ) == ["نیازمندی‌ها.docx"]
    assert resolve_target_files("هر سوالی", available, explicit_filter=[]) == []

    # Specific file mention
    assert resolve_target_files("در فایل گزارش اول چه مواردی ذکر شده؟", available) == [
        "گزارش اول.docx"
    ]
    assert resolve_target_files("بر اساس نیازمندی‌ها، سناریوها را بگو", available) == [
        "نیازمندی‌ها.docx"
    ]

    # Broad multi-file intent (should return None to query all files)
    assert (
        resolve_target_files("یک خلاصه جامع از هر سه فایل ارائه بده", available) is None
    )
    assert resolve_target_files("نتیجه‌گیری کلی و مقایسه اسناد", available) is None
    assert resolve_target_files("جمع‌بندی نهایی از کل اسناد", available) is None


def test_format_multi_doc_context_structure() -> None:
    """Verifies that multi-document nodes are clearly partitioned by filename."""
    nodes = [
        ExtractedNode(
            text="Text from Doc 1", score=0.9, metadata={"filename": "doc1.docx"}
        ),
        ExtractedNode(
            text="Text from Doc 2", score=0.85, metadata={"filename": "doc2.docx"}
        ),
    ]
    formatted = format_multi_doc_context(nodes)
    assert "=== سند 1: doc1.docx ===" in formatted
    assert "=== سند 2: doc2.docx ===" in formatted
    assert "Text from Doc 1" in formatted
    assert "Text from Doc 2" in formatted


def test_context_exposes_reliable_location_to_the_model() -> None:
    formatted = format_multi_doc_context(
        [
            ExtractedNode(
                text="Located text",
                score=0.9,
                metadata={"filename": "guide.pdf", "page": 7},
            )
        ]
    )
    assert "[source: guide.pdf, page: 7]" in formatted


@patch("backend.core.strategies.strict_rag.Settings")
def test_strict_rag_balanced_multi_file_retrieval(mock_settings: MagicMock) -> None:
    """Verifies that Strict RAG performs balanced per-file retrieval across 3 session files."""
    mock_repo = MagicMock()
    mock_repo.get_session_files.return_value = [
        "fileA.docx",
        "fileB.docx",
        "fileC.docx",
    ]

    # Mock similarity search returning distinct nodes for each file
    def mock_similarity(
        query: str,
        top_k: int = 15,
        session_id: str | None = None,
        file_filter: list[str] | None = None,
    ) -> list[ExtractedNode]:
        fn = file_filter[0] if file_filter else "unknown"
        return [
            ExtractedNode(
                text=f"Content of {fn} chunk {i}", score=0.85, metadata={"filename": fn}
            )
            for i in range(1, top_k + 1)
        ]

    mock_repo.similarity_search.side_effect = mock_similarity

    mock_llm = MagicMock()
    mock_llm.complete.return_value = "Comprehensive 3-file synthesis."
    mock_settings.llm = mock_llm

    strategy = StrictRAGStrategy(repo=mock_repo, default_top_k=15)
    # Query asks for an overarching summary across all files
    res = strategy.execute(
        "خلاصه جامع از هر سه فایل ارائه دهید", [], session_id="session-3files", top_k=15
    )

    assert res.answer == "Comprehensive 3-file synthesis."
    # With 3 files and top_k=15, k_per_file = 15 // 3 = 5 per file -> total 15 chunks
    assert len(res.source_nodes) == 15
    filenames = {n.metadata.get("filename") for n in res.source_nodes}
    assert filenames == {"fileA.docx", "fileB.docx", "fileC.docx"}

    called_prompt = mock_llm.complete.call_args[0][0]
    assert "=== سند 1: fileA.docx ===" in called_prompt
    assert "=== سند 2: fileB.docx ===" in called_prompt
    assert "=== سند 3: fileC.docx ===" in called_prompt


@patch("backend.api.routes.CondenseQuestionPipeline")
@patch("backend.api.routes.get_query_strategy")
def test_query_route_with_file_filter(
    mock_get_strategy: MagicMock, mock_condenser_cls: MagicMock
) -> None:
    """Verifies that QueryRequest with file_filter properly forwards to strategy."""
    mock_condenser = MagicMock()
    mock_condenser.condense.return_value = "condensed query"
    mock_condenser_cls.return_value = mock_condenser

    mock_strategy = MagicMock()
    mock_strategy.execute.return_value = QueryResponse(
        answer="Targeted answer for file2", source_nodes=[]
    )
    mock_get_strategy.return_value = mock_strategy

    payload = {
        "prompt": "What is in file 2?",
        "mode": "strict",
        "session_id": "session-123",
        "file_filter": ["file2.docx"],
    }

    response = client.post("/query", json=payload)

    assert response.status_code == 200
    assert response.json()["answer"] == "Targeted answer for file2"
    mock_strategy.execute.assert_called_once_with(
        query="condensed query",
        chat_history=[],
        session_id="session-123",
        top_k=None,
        file_filter=["file2.docx"],
    )
