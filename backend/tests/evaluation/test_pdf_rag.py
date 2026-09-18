"""Tests for deterministic PDF evaluation scoring."""

from backend.core.models.domain import ExtractedNode
from backend.tests.evaluation.scoring import (
    is_strict_refusal,
    normalize_text,
    score_answer,
)


def test_normalize_text_unifies_persian_variants() -> None:
    """Persian glyph and half-space variants do not alter fact matching."""
    assert normalize_text("کلید\u200cهای يکسان") == "کلید های یکسان"


def test_score_answer_requires_fact_and_provenance_matches() -> None:
    """Fact coverage, filename, and page evidence are scored independently."""
    score = score_answer(
        "PKCE از code_verifier و SHA-256 استفاده می‌کند.",
        [
            {"any_of": ["code_verifier"]},
            {"any_of": ["SHA-256", "S256"]},
            {"any_of": ["code_challenge"]},
        ],
        [
            ExtractedNode(
                text="evidence",
                metadata={"filename": "report.pdf", "page": 14},
                score=0.9,
            )
        ],
        filename="report.pdf",
        page=14,
    )

    assert score.fact_coverage == 2 / 3
    assert score.expected_file_cited is True
    assert score.expected_page_cited is True


def test_strict_refusal_recognizes_bilingual_contract() -> None:
    """Both documented Persian and English refusals are accepted."""
    assert is_strict_refusal("بر اساس اسناد ارائه شده، پاسخی برای این سوال ندارم.")
    assert is_strict_refusal("I do not know based on the provided documents.")
    assert not is_strict_refusal("Canberra is the capital of Australia.")
