"""Prompt budgeting keeps grounding rules inside small context windows."""

from unittest.mock import MagicMock

from backend.core.domain.documents import ExtractedNode
from backend.core.service.context_budget import (
    UNKNOWN_CONTEXT_WINDOW,
    answer_reserve,
    estimate_tokens,
    fit_to_context,
    model_context_window,
)

PERSIAN_CHUNK = "این یک بخش آزمایشی از سند فارسی است. " * 40


def _node(text: str, score: float, name: str) -> ExtractedNode:
    return ExtractedNode(text=text, metadata={"filename": name}, score=score)


def test_persian_counts_more_tokens_than_latin_of_equal_length() -> None:
    assert estimate_tokens("ا" * 100) > estimate_tokens("a" * 100)
    assert estimate_tokens("") == 0


def test_answer_reserve_scales_with_the_window() -> None:
    assert answer_reserve(2048) == 512
    assert answer_reserve(32768) == 1024
    assert answer_reserve(512) == 256


def test_lowest_scores_are_dropped_and_order_is_kept() -> None:
    """A 4k window keeps the best chunks in their original order."""
    nodes = [
        _node(PERSIAN_CHUNK, 0.70, "a"),
        _node(PERSIAN_CHUNK, 0.90, "b"),
        _node(PERSIAN_CHUNK, 0.80, "c"),
        _node(PERSIAN_CHUNK, 0.60, "d"),
    ]
    per_chunk = estimate_tokens(PERSIAN_CHUNK) + 24
    window = 1024 + 100 + per_chunk * 2 + 10

    kept = fit_to_context(nodes, context_window=window, fixed_prompt="x" * 350)

    assert [node.metadata["filename"] for node in kept] == ["b", "c"]


def test_large_windows_keep_every_chunk() -> None:
    nodes = [_node(PERSIAN_CHUNK, 0.5, str(index)) for index in range(15)]
    assert fit_to_context(nodes, context_window=32768, fixed_prompt="rules") == nodes


def test_one_oversized_chunk_is_shortened_instead_of_dropped() -> None:
    """The model always receives some evidence, cut to fit."""
    huge = _node(PERSIAN_CHUNK * 20, 0.9, "big")

    kept = fit_to_context([huge], context_window=2048, fixed_prompt="rules")

    assert len(kept) == 1
    assert 0 < len(kept[0].text) < len(huge.text)
    assert kept[0].metadata == {"filename": "big"}
    assert fit_to_context([], context_window=2048, fixed_prompt="") == []


def test_context_window_is_read_from_the_model_adapter() -> None:
    llm = MagicMock()
    llm.metadata.context_window = 8192
    assert model_context_window(llm) == 8192
    assert model_context_window(MagicMock()) == UNKNOWN_CONTEXT_WINDOW
    assert model_context_window(object()) == UNKNOWN_CONTEXT_WINDOW
