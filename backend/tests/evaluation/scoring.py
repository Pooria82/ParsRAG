"""Deterministic scoring primitives for live PDF RAG evaluations."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import TypedDict

from backend.core.models.domain import ExtractedNode


class ExpectedFact(TypedDict):
    """One fact expressed by one or more acceptable textual variants."""

    any_of: list[str]


@dataclass(frozen=True)
class AnswerScore:
    """Deterministic evidence collected for one generated answer."""

    fact_coverage: float
    matched_facts: int
    total_facts: int
    expected_file_cited: bool
    expected_page_cited: bool


_PERSIAN_TRANSLATION = str.maketrans({"ي": "ی", "ك": "ک", "ۀ": "ه"})
_REFUSAL_MARKERS = (
    "پاسخی برای این سوال ندارم",
    "پاسخی برای این سوال در متن یافت نشد",
    "هیچ سند مرتبطی یافت نشد",
    "i do not know based on the provided documents",
    "no relevant documents found",
)


def normalize_text(value: str) -> str:
    """Normalize Persian/English output for stable lexical scoring."""
    normalized = unicodedata.normalize("NFKC", value).translate(_PERSIAN_TRANSLATION)
    normalized = normalized.casefold().replace("\u200c", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def is_strict_refusal(answer: str) -> bool:
    """Return whether strict mode used one of its documented refusals."""
    normalized = normalize_text(answer)
    return any(normalize_text(marker) in normalized for marker in _REFUSAL_MARKERS)


def score_answer(
    answer: str,
    expected_facts: list[ExpectedFact],
    sources: list[ExtractedNode],
    *,
    filename: str,
    page: int,
) -> AnswerScore:
    """Score fact coverage and provenance without using an LLM judge."""
    normalized_answer = normalize_text(answer)
    matched = sum(
        any(normalize_text(term) in normalized_answer for term in fact["any_of"])
        for fact in expected_facts
    )
    total = len(expected_facts)
    normalized_filename = normalize_text(filename)
    matching_sources = [
        source
        for source in sources
        if normalize_text(str(source.metadata.get("filename", "")))
        == normalized_filename
    ]
    return AnswerScore(
        fact_coverage=(matched / total if total else 1.0),
        matched_facts=matched,
        total_facts=total,
        expected_file_cited=bool(matching_sources),
        expected_page_cited=any(
            source.metadata.get("page") == page for source in matching_sources
        ),
    )
