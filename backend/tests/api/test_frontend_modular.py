"""Unit tests for the modularized frontend components: models, builders, services, and handlers."""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from chainlit.input_widget import Select

from frontend.config import FrontendConfig
from frontend.handlers.query_handler import QueryHandler
from frontend.handlers.upload_handler import UploadHandler
from frontend.models import CitationItem, SessionState, UploadItem
from frontend.services.session_manager import SessionManager
from frontend.ui.citation_builder import CitationBuilder
from frontend.ui.settings_builder import SettingsBuilder


def test_frontend_config_defaults() -> None:
    """Verifies default configuration values and operational boundaries."""
    cfg = FrontendConfig()
    assert cfg.max_files_per_batch == 5
    assert cfg.max_file_size_bytes == 50 * 1024 * 1024
    assert ".docx" in cfg.supported_extensions
    assert ".pptx" in cfg.supported_extensions
    assert ".pdf" in cfg.supported_extensions
    assert cfg.default_top_k == 15
    assert cfg.min_top_k == 5
    assert cfg.max_top_k == 30
    assert cfg.step_top_k == 1


def test_upload_item_model() -> None:
    """Verifies UploadItem model instantiation and size calculation."""
    item = UploadItem(filename="test_doc.docx", content=b"Hello World")
    assert item.filename == "test_doc.docx"
    assert item.size_bytes == 11


def test_citation_item_model() -> None:
    """Verifies CitationItem model validation and attributes."""
    cit = CitationItem(
        index=1,
        filename="report.pdf",
        score=0.912,
        text="Sample extracted text",
        title="منبع 1: report.pdf",
        body="Excerpt markdown",
    )
    assert cit.index == 1
    assert cit.filename == "report.pdf"
    assert cit.score == 0.912


def test_session_state_model() -> None:
    """Verifies SessionState serialization and default values."""
    state = SessionState(session_id="session_abc123")
    assert state.session_id == "session_abc123"
    assert state.mode == "hybrid"
    assert state.top_k is None
    assert state.chat_history == []
    assert state.uploaded_files == []

    d = state.to_dict()
    assert d["session_id"] == "session_abc123"
    assert d["mode"] == "hybrid"
    assert d["top_k"] is None


def test_session_manager_isolated_store() -> None:
    """Verifies SessionManager behavior using an isolated in-memory dictionary store."""
    mock_store: dict[str, Any] = {}
    manager = SessionManager(store=mock_store)

    # 1. Initialize with explicit top_k
    state = manager.initialize_session(
        session_id="test_sess_42", default_mode="strict", default_top_k=20
    )
    assert state.session_id == "test_sess_42"
    assert state.mode == "strict"
    assert state.top_k == 20

    # 2. Mode mutation
    manager.set_mode("llm-only")
    assert manager.get_mode() == "llm-only"

    # 3. Top_k mutation (including None for dynamic optimization)
    manager.set_top_k(25)
    assert manager.get_top_k() == 25
    manager.set_top_k(None)
    assert manager.get_top_k() is None

    # 4. Uploaded files tracking
    added = manager.add_uploaded_files(["doc1.docx", "doc2.pdf"])
    assert added == ["doc1.docx", "doc2.pdf"]
    # Adding duplicate should not duplicate entry
    added_again = manager.add_uploaded_files(["doc2.pdf", "doc3.pptx"])
    assert added_again == ["doc1.docx", "doc2.pdf", "doc3.pptx"]
    assert manager.get_uploaded_files() == ["doc1.docx", "doc2.pdf", "doc3.pptx"]

    # 5. Conversational history tracking with truncation
    manager.append_chat_turn("Q1", "A1", max_turns=4)
    manager.append_chat_turn("Q2", "A2", max_turns=4)
    history = manager.get_chat_history()
    assert len(history) == 4
    assert history[0]["content"] == "Q1"

    # Adding a 3rd turn (2 more messages) should truncate to last 4 messages
    manager.append_chat_turn("Q3", "A3", max_turns=4)
    truncated = manager.get_chat_history()
    assert len(truncated) == 4
    assert truncated[0]["content"] == "Q2"
    assert truncated[-1]["content"] == "A3"


def test_citation_builder() -> None:
    """Verifies CitationBuilder parsing and Chainlit element generation."""
    builder = CitationBuilder()

    nodes: list[dict[str, Any]] = [
        {
            "text": "بخشی از گزارش مالی سال ۱۴۰۲",
            "metadata": {"filename": "finance.docx"},
            "score": 0.884,
        },
        {
            "text": "بدون متادیتا و نمره",
        },
    ]

    elements = builder.build_elements(nodes, thread_id="test_thread_123")
    assert len(elements) == 2
    assert "finance.docx" in elements[0].name
    assert "0.884" in elements[0].content
    assert "سند نامشخص" in elements[1].name
    assert "بدون امتیاز عددی" in elements[1].content


def test_settings_builder() -> None:
    """Verifies SettingsBuilder creates valid ChatSettings with all 7 in-app configurable widgets."""
    builder = SettingsBuilder()
    settings = builder.build(lang="fa")
    assert len(settings.inputs) == 7

    input_ids = [inp.id for inp in settings.inputs]
    assert input_ids == [
        "language",
        "mode",
        "strict_rag_threshold",
        "dynamic_depth",
        "manual_top_k",
        "max_history_turns",
        "backend_url",
    ]

    lang_widget = settings.inputs[0]
    assert isinstance(lang_widget, Select)
    assert "English" in lang_widget.values

    mode_widget = settings.inputs[1]
    assert isinstance(mode_widget, Select)
    assert any("ترکیبی" in v for v in mode_widget.values)

    # Test English build
    settings_en = builder.build(lang="en")
    assert len(settings_en.inputs) == 7
    mode_widget_en = settings_en.inputs[1]
    assert isinstance(mode_widget_en, Select)
    assert "Hybrid RAG" in mode_widget_en.values


def test_upload_handler_validation() -> None:
    """Verifies UploadHandler validation rules for file limits, types, and sizes."""
    mock_client = AsyncMock()
    mock_store: dict[str, Any] = {}
    manager = SessionManager(store=mock_store)
    handler = UploadHandler(client=mock_client, session_manager=manager)

    # 1. Reject unsupported extension
    bad_ext = [UploadItem(filename="script.sh", content=b"echo 1")]
    with pytest.raises(ValueError, match="فرمت فایل 'script.sh' مجاز نیست"):
        handler.validate_items(bad_ext, existing_count=0)

    # 2. Reject oversized file (> 50 MB)
    huge_file = [
        UploadItem(filename="large.pdf", content=b"0" * (50 * 1024 * 1024 + 1))
    ]
    with pytest.raises(ValueError, match="مگابایت بیشتر است"):
        handler.validate_items(huge_file, existing_count=0)

    # 3. Reject cumulative count > 5
    four_files = [
        UploadItem(filename=f"doc_{i}.docx", content=b"text") for i in range(4)
    ]
    with pytest.raises(ValueError, match="حداکثر 5 فایل"):
        handler.validate_items(four_files, existing_count=2)


@pytest.mark.asyncio
async def test_upload_handler_extraction() -> None:
    """Verifies UploadHandler extract_upload_items from mock Chainlit elements."""
    mock_client = AsyncMock()
    mock_store: dict[str, Any] = {}
    manager = SessionManager(store=mock_store)
    handler = UploadHandler(client=mock_client, session_manager=manager)

    class MockElement:
        def __init__(self, name: str, content: bytes | None, path: str | None) -> None:
            self.name = name
            self.content = content
            self.path = path

    elements = [
        MockElement(name="in_memory.pdf", content=b"pdf bytes", path=None),
    ]

    items = await handler.extract_upload_items(elements)
    assert len(items) == 1
    assert items[0].filename == "in_memory.pdf"
    assert items[0].content == b"pdf bytes"


@pytest.mark.asyncio
async def test_query_handler_skips_empty_prompt() -> None:
    """Verifies QueryHandler immediately ignores empty or whitespace prompts."""
    mock_client = AsyncMock()
    mock_store: dict[str, Any] = {}
    manager = SessionManager(store=mock_store)
    handler = QueryHandler(client=mock_client, session_manager=manager)

    # Empty string should not invoke backend query
    await handler.handle_query("   ")
    mock_client.query.assert_not_called()
