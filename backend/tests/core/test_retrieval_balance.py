"""Specific questions search all files together; summaries keep a share per file."""

from typing import cast

from backend.core.domain.documents import ExtractedNode
from backend.core.port.document_repository import DocumentRepository
from backend.core.strategies.multi_doc_utils import retrieve_document_nodes

FILES = ["report.docx", "final.docx", "fixes-1.docx", "fixes-2.docx"]


class Repo:
    """Fake repository: the answer lives in report.docx (and a copy in final.docx)."""

    def __init__(self) -> None:
        """Record every search as (top_k, file_filter)."""
        self.calls: list[tuple[int, list[str] | None]] = []

    def similarity_search(
        self,
        query: str,
        top_k: int = 5,
        session_id: str | None = None,
        file_filter: list[str] | None = None,
    ) -> list[ExtractedNode]:
        """Return the best-scored passages, optionally from the named files only."""
        self.calls.append((top_k, file_filter))
        corpus = [
            ExtractedNode(
                text=f"Report › Setup\nstep {i} of the setup",
                score=0.9 - i / 100,
                metadata={"filename": "report.docx", "paragraph": 100 + i},
            )
            for i in range(6)
        ] + [
            ExtractedNode(
                text="Final › Phase 4 › Setup\nstep 0 of the setup",
                score=0.88,
                metadata={"filename": "final.docx", "paragraph": 2000},
            ),
            ExtractedNode(
                text="unrelated correction",
                score=0.6,
                metadata={"filename": "fixes-1.docx", "paragraph": 3},
            ),
            ExtractedNode(
                text="another correction",
                score=0.58,
                metadata={"filename": "fixes-2.docx", "paragraph": 7},
            ),
        ]
        hits = [
            n
            for n in corpus
            if file_filter is None or n.metadata["filename"] in file_filter
        ]
        return sorted(hits, key=lambda n: -(n.score or 0))[:top_k]


def test_specific_questions_let_the_answering_file_contribute_most_excerpts() -> None:
    repo = Repo()

    nodes = retrieve_document_nodes(
        cast(DocumentRepository, repo), "which model is pulled?", FILES, None, "s", 6, 3
    )

    report = [n for n in nodes if n.metadata["filename"] == "report.docx"]
    assert len(report) == 5
    assert repo.calls[0] == (6, None)
    # Every other file still contributes its best excerpt; final.docx only
    # repeats report.docx, so its copy is dropped.
    assert {n.metadata["filename"] for n in nodes} == {
        "report.docx",
        "fixes-1.docx",
        "fixes-2.docx",
    }


def test_identical_passages_from_two_files_are_kept_once() -> None:
    repo = Repo()

    nodes = retrieve_document_nodes(
        cast(DocumentRepository, repo), "which model is pulled?", FILES, None, "s", 6, 3
    )

    copies = [n for n in nodes if n.text.endswith("step 0 of the setup")]
    assert len(copies) == 1 and copies[0].metadata["filename"] == "report.docx"


def test_summaries_still_take_a_share_from_every_file() -> None:
    repo = Repo()

    retrieve_document_nodes(
        cast(DocumentRepository, repo), "مقایسه همه اسناد", FILES, None, "s", 8, 2
    )

    assert [call[1] for call in repo.calls] == [[name] for name in FILES]
