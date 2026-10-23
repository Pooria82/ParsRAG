"""Tests for deterministic PDF evaluation scoring and the evaluation runner."""

from pathlib import Path

import pymupdf
import pytest

from backend.api.dependencies import get_ingest_documents
from backend.core.domain.documents import ExtractedNode
from backend.tests.core.use_case.fakes import InMemoryRepository
from backend.tests.evaluation.run_pdf_evaluation import _ingest
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
    assert score.passes() is True


def test_strict_refusal_recognizes_bilingual_contract() -> None:
    """Both documented Persian and English refusals are accepted."""
    assert is_strict_refusal("بر اساس اسناد ارائه شده، پاسخی برای این سوال ندارم.")
    assert is_strict_refusal("I do not know based on the provided documents.")
    assert not is_strict_refusal("Canberra is the capital of Australia.")


def test_the_runner_indexes_through_the_ingestion_use_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pages keep their numbers and are bridged, as in an upload."""
    monkeypatch.setenv("OCR_ENABLED", "0")
    document = pymupdf.open()
    for _ in range(2):
        document.new_page()
    document[0].insert_text((72, 72), "Tokens are signed with RS256 and")
    document[1].insert_text((72, 72), "expire after fifteen minutes.")
    pdf = tmp_path / "report.pdf"
    document.save(pdf)
    repository = InMemoryRepository()

    indexed = _ingest(get_ingest_documents(repository), pdf, "pdf-eval-01")

    assert (indexed.filename, indexed.sections) == ("report.pdf", 2)
    nodes = repository.sessions["pdf-eval-01"]
    # The page-boundary bridge joins the end of page 1 to the start of page 2.
    assert any("RS256 and" in n.text and "fifteen minutes" in n.text for n in nodes)
    pages = {node.metadata.get("page") for node in nodes}
    assert {1, 2} <= pages
