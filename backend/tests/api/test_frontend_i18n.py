"""Automated unit tests for frontend internationalization (i18n) and bilingual session settings."""

from typing import Any

import pytest

from frontend.models import CitationItem, SessionState
from frontend.services.session_manager import SessionManager
from frontend.ui.citation_builder import CitationBuilder
from frontend.ui.i18n import (
    LANG_EN,
    LANG_FA,
    format_citation_body,
    format_citation_title,
    get_mode_options,
    get_welcome_markdown,
    normalize_language,
)


@pytest.mark.parametrize(
    ("input_code", "expected"),
    [
        ("fa", LANG_FA),
        ("fa-IR", LANG_FA),
        ("persian", LANG_FA),
        ("en", LANG_EN),
        ("en-US", LANG_EN),
        ("English", LANG_EN),
        ("", LANG_FA),
        (None, LANG_FA),
    ],
)
def test_normalize_language(input_code: str | None, expected: str) -> None:
    """Language normalization standardizes all inputs to 'fa' or 'en'."""
    assert normalize_language(input_code) == expected


def test_bilingual_welcome_markdown() -> None:
    """Welcome markdown contains language-appropriate greetings and instructions."""
    welcome_fa = get_welcome_markdown(LANG_FA)
    assert "خوش آمدید" in welcome_fa
    assert "Strict RAG" in welcome_fa

    welcome_en = get_welcome_markdown(LANG_EN)
    assert "Welcome to ParsRAG" in welcome_en
    assert "Strict RAG (Document-Grounded)" in welcome_en


def test_bilingual_mode_options() -> None:
    """Mode selection options are rendered in both Persian and English."""
    options_fa = get_mode_options(LANG_FA)
    assert any("ترکیبی" in opt for opt in options_fa)

    options_en = get_mode_options(LANG_EN)
    assert "Hybrid RAG" in options_en
    assert "Strict RAG" in options_en
    assert "LLM Only" in options_en


def test_bilingual_citation_formatting() -> None:
    """Citations generate proper localized headers and score chips."""
    title_fa = format_citation_title(LANG_FA, 1, "test.docx")
    assert title_fa == "منبع 1: test.docx"

    title_en = format_citation_title(LANG_EN, 1, "test.docx")
    assert title_en == "Source 1: test.docx"

    body_fa = format_citation_body(
        LANG_FA, text="نمونه", score=0.891, filename="test.docx"
    )
    assert "امتیاز شباهت" in body_fa
    assert "0.8910" in body_fa

    body_en = format_citation_body(
        LANG_EN, text="Sample", score=0.891, filename="test.docx"
    )
    assert "Similarity Score" in body_en
    assert "0.8910" in body_en


def test_citation_builder_with_language() -> None:
    """CitationBuilder builds elements respecting the active session language."""
    builder = CitationBuilder()
    raw_node: dict[str, Any] = {
        "text": "Report content",
        "metadata": {"filename": "annual.pdf"},
        "score": 0.94,
    }

    item_en: CitationItem = builder.parse_node(raw_node, index=1, lang=LANG_EN)
    assert item_en.title == "Source 1: annual.pdf"
    assert "Similarity Score" in item_en.body

    item_fa: CitationItem = builder.parse_node(raw_node, index=2, lang=LANG_FA)
    assert item_fa.title == "منبع 2: annual.pdf"
    assert "امتیاز شباهت" in item_fa.body


def test_session_manager_comprehensive_settings() -> None:
    """SessionManager initializes and updates all in-app configurable settings."""
    mock_store: dict[str, Any] = {}
    sm = SessionManager(store=mock_store)

    state: SessionState = sm.initialize_session(
        session_id="test_sess_i18n",
        default_language=LANG_EN,
        default_mode="strict",
        default_strict_rag_threshold=0.85,
        default_dynamic_top_k=False,
        default_manual_top_k=18,
        default_top_k=18,
        default_max_chat_history_turns=12,
        default_backend_url="http://127.0.0.1:8000",
    )

    assert state.language == LANG_EN
    assert state.mode == "strict"
    assert state.strict_rag_threshold == 0.85
    assert not state.dynamic_top_k
    assert state.manual_top_k == 18
    assert state.top_k == 18
    assert state.max_chat_history_turns == 12
    assert state.backend_url == "http://127.0.0.1:8000"

    # Mutate language
    sm.set_language(LANG_FA)
    assert sm.get_language() == LANG_FA

    # Mutate threshold
    sm.set_strict_rag_threshold(0.72)
    assert sm.get_strict_rag_threshold() == 0.72

    # Mutate dynamic top-k
    sm.set_dynamic_top_k(True)
    assert sm.get_dynamic_top_k() is True
    sm.set_top_k(None)
    assert sm.get_top_k() is None

    # Mutate backend URL
    sm.set_backend_url("http://custom-host:9000")
    assert sm.get_backend_url() == "http://custom-host:9000"
