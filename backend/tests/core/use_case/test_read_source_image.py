"""Reading the preview of a cited image."""

import pytest

from backend.core.domain.exceptions import InvalidInputError, NotFoundError
from backend.core.use_case.session.read_source_image import ReadSourceImage
from backend.tests.core.use_case.fakes import InMemoryRepository


def test_a_stored_preview_is_returned() -> None:
    repository = InMemoryRepository()
    repository.save_images("session-1", "report.docx", {4: b"webp"})

    assert ReadSourceImage(repository).execute("session-1", "report.docx", 4) == b"webp"


def test_a_missing_preview_is_not_found() -> None:
    with pytest.raises(NotFoundError):
        ReadSourceImage(InMemoryRepository()).execute("session-1", "report.docx", 4)


@pytest.mark.parametrize(
    ("session_id", "filename", "number"),
    [("../x", "report.docx", 1), ("session-1", "", 1), ("session-1", "a.docx", 0)],
)
def test_invalid_references_are_rejected(
    session_id: str, filename: str, number: int
) -> None:
    with pytest.raises(InvalidInputError):
        ReadSourceImage(InMemoryRepository()).execute(session_id, filename, number)
