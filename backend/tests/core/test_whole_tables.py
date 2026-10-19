"""A retrieved table chunk brings the rest of its table into the context."""

from unittest.mock import MagicMock

from backend.core.domain.documents import ExtractedNode
from backend.core.strategies.multi_doc_utils import with_whole_tables
from backend.infrastructure.database.keyword_index import SessionCorpus
from backend.infrastructure.database.qdrant_repo import QdrantRepository
from backend.tests.core.use_case.fakes import InMemoryRepository


def _chunk(
    text: str, table: int | None = None, name: str = "report.docx"
) -> ExtractedNode:
    metadata: dict[str, object] = {"filename": name, "paragraph": 823}
    if table is not None:
        metadata["table"] = table
    return ExtractedNode(text=text, metadata=metadata, score=0.8)


def test_other_chunks_of_a_retrieved_table_follow_it() -> None:
    repo = InMemoryRepository()
    rows = [_chunk("| ابزار | ستاره |\n| :--- | :--- |\n| Selenium IDE | 2.9k |", 6)]
    rows += [_chunk("- سطر 9: [ابزار]: PyAutoGUI | [ستاره]: 10.9k", 6)]
    other = _chunk("جدول دیگر", 7)
    repo.save_nodes([*rows, other, _chunk("متن")], "s")
    retrieved = [rows[0], _chunk("متن")]

    result = with_whole_tables(repo, retrieved, "s")

    assert [n.text for n in result] == [rows[0].text, rows[1].text, "متن"]
    assert result[1].score == rows[0].score


def test_tables_are_completed_once_and_without_a_session_nothing_changes() -> None:
    repo = InMemoryRepository()
    first, second = _chunk("الف", 2), _chunk("ب", 2)
    repo.save_nodes([first, second], "s")

    assert [n.text for n in with_whole_tables(repo, [first, second], "s")] == [
        "الف",
        "ب",
    ]
    assert with_whole_tables(repo, [first], None) == [first]


def test_qdrant_returns_a_tables_chunks_grid_first_then_rows_in_order() -> None:
    repo = QdrantRepository.__new__(QdrantRepository)
    corpus = SessionCorpus(
        ids=[1, 2, 3, 4],
        texts=["- سطر 7: ...", "| a |\n| :--- |", "- سطر 2: ...", "other"],
        payloads=[
            {"filename": "r.docx", "table": 6},
            {"filename": "r.docx", "table": 6},
            {"filename": "r.docx", "table": 6},
            {"filename": "r.docx", "table": 5},
        ],
    )
    repo.__dict__["_keyword_cache"] = MagicMock(get=MagicMock(return_value=corpus))

    chunks = repo.section_chunks("s", "r.docx", "table", 6)

    assert [c.text for c in chunks] == [
        "| a |\n| :--- |",
        "- سطر 2: ...",
        "- سطر 7: ...",
    ]
