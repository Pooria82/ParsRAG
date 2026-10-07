"""Citation numbers are read from answers in Persian and English."""

from unittest.mock import MagicMock, patch

from backend.core.domain.documents import ExtractedNode
from backend.core.service.citations import extract_citations
from backend.core.strategies.strict_rag import StrictRAGStrategy


def test_numbers_are_read_in_first_use_order_without_duplicates() -> None:
    answer = "Fact one [2]. Fact two [1][2]. Both [3, 1]. Persian [۴]، و [۲،۵]."
    assert extract_citations(answer, 5) == [2, 1, 3, 4, 5]


def test_out_of_range_and_non_citation_brackets_are_ignored() -> None:
    answer = "See [0], [9], [page 3], array[1000] and [a]. Real [1]."
    assert extract_citations(answer, 2) == [1]
    assert extract_citations("no citations", 3) == []


@patch("backend.core.strategies.strict_rag.Settings")
def test_strict_answers_report_which_sources_they_cite(
    mock_settings: MagicMock,
) -> None:
    repo = MagicMock()
    repo.get_session_files.return_value = ["a.pdf"]
    repo.similarity_search.return_value = [
        ExtractedNode(text="first", score=0.91, metadata={"filename": "a.pdf"}),
        ExtractedNode(text="second", score=0.9, metadata={"filename": "a.pdf"}),
    ]
    mock_settings.llm.complete.return_value = "پاسخ بر اساس بخش دوم [2]."

    result = StrictRAGStrategy(repo).execute("پرسش", [], session_id="s")

    assert result.cited == [2]
    assert [node.text for node in result.source_nodes] == ["first", "second"]
    prompt = mock_settings.llm.complete.call_args.args[0]
    assert "[1] a.pdf\nfirst" in prompt and "[2] a.pdf\nsecond" in prompt
