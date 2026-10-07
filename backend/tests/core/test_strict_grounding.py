"""Strict mode answers by meaning and refuses only without relevant evidence."""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.domain.documents import ExtractedNode
from backend.core.strategies.hybrid_rag import HYBRID_RAG_PROMPT_TEMPLATE
from backend.core.strategies.llm_only import LLM_ONLY_PROMPT_TEMPLATE
from backend.core.strategies.prompt_rules import FORMATTING_RULES
from backend.core.strategies.strict_rag import (
    DEFAULT_STRICT_THRESHOLD,
    STRICT_RAG_PROMPT_TEMPLATE,
    StrictRAGStrategy,
    _has_lexical_evidence,
    is_document_overview_question,
)


@pytest.fixture(autouse=True)
def default_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the shipped default threshold."""
    monkeypatch.delenv("STRICT_RAG_THRESHOLD", raising=False)
    monkeypatch.delenv("STRICT_RAG_TOP_K", raising=False)
    monkeypatch.delenv("RAG_TOP_K", raising=False)


@pytest.mark.parametrize(
    "question",
    [
        "این سند درباره چیست؟",
        "موضوع اصلی این فایل را بگو",
        "خلاصه‌ای از این گزارش بده",
        "چکیده مقاله را بگو",
        "این فایل چه نوع سندی است؟",
        "What is this document about?",
        "Summarize the report",
    ],
)
def test_document_overview_questions_are_recognized(question: str) -> None:
    assert is_document_overview_question(question)


@pytest.mark.parametrize(
    "question",
    ["PKCE چگونه کار می‌کند؟", "رتبه Python در TIOBE چند است؟", "How does RTR work?"],
)
def test_specific_questions_are_not_overviews(question: str) -> None:
    assert not is_document_overview_question(question)


def _node(text: str, score: float) -> ExtractedNode:
    return ExtractedNode(
        text=text, metadata={"filename": "exam.pdf", "page": 2}, score=score
    )


@patch("backend.core.strategies.strict_rag.Settings")
def test_overview_question_reaches_the_model_despite_low_scores(
    mock_settings: MagicMock,
) -> None:
    repo = MagicMock()
    repo.get_session_files.return_value = ["exam.pdf"]
    repo.similarity_search.return_value = [
        _node("سوال ۱: مشتق تابع sin را بنویسید.", 0.70)
    ]
    mock_settings.llm.complete.return_value = "این سند یک آزمون ریاضی است."

    result = StrictRAGStrategy(repo).execute("این سند درباره چیست؟", [], session_id="s")

    assert result.answer == "این سند یک آزمون ریاضی است."
    mock_settings.llm.complete.assert_called_once()


@patch("backend.core.strategies.strict_rag.Settings")
def test_unrelated_low_score_question_is_still_refused(
    mock_settings: MagicMock,
) -> None:
    repo = MagicMock()
    repo.get_session_files.return_value = ["exam.pdf"]
    repo.similarity_search.return_value = [
        _node("سوال ۱: مشتق تابع sin را بنویسید.", 0.70)
    ]

    result = StrictRAGStrategy(repo).execute(
        "طول nonce در AES-GCM چند بیت است؟", [], session_id="s"
    )

    assert "ندارم" in result.answer
    mock_settings.llm.complete.assert_not_called()


def test_lexical_evidence_treats_persian_and_latin_digits_alike() -> None:
    nodes = [_node("زبان Python با 15 درصد در رتبه اول قرار دارد", 0.70)]

    assert _has_lexical_evidence("سهم زبان Python ۱۵ درصد است؟", nodes, 0.75)


def test_default_threshold_matches_calibration() -> None:
    assert DEFAULT_STRICT_THRESHOLD == 0.75


def test_strict_prompt_allows_meaning_based_partial_answers() -> None:
    prompt = STRICT_RAG_PROMPT_TEMPLATE
    assert "Match by meaning, not by exact wording" in prompt
    assert "answer that part" in prompt
    assert "Never add outside knowledge" in prompt
    assert "پاسخی برای این سوال در متن یافت نشد" in prompt


@pytest.mark.parametrize(
    "template",
    [STRICT_RAG_PROMPT_TEMPLATE, HYBRID_RAG_PROMPT_TEMPLATE, LLM_ONLY_PROMPT_TEMPLATE],
)
def test_every_mode_asks_for_renderable_math(template: str) -> None:
    assert FORMATTING_RULES in template
    assert "Keep Persian words outside math delimiters" in template
