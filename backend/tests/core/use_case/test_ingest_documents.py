"""Ingestion use-case rules exercised without FastAPI, Qdrant, or parsers."""

import io
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest

from backend.core.domain.documents import ParsedSection
from backend.core.domain.exceptions import (
    ConflictError,
    InvalidInputError,
    PayloadTooLargeError,
)
from backend.core.domain.upload_policy import UploadPolicy
from backend.core.dto.input.ingestion import IncomingFile, IngestDocumentsCommand
from backend.core.dto.output.common import MessageResponse
from backend.core.runtime.capacity import WorkLimiter
from backend.core.runtime.session_locks import SessionLocks
from backend.core.use_case.ingestion.ingest_documents import IngestDocuments
from backend.tests.core.use_case.fakes import (
    FakeChunker,
    FakeParser,
    InMemoryRepository,
)

PDF = b"%PDF-1.4 body"
SMALL_POLICY = UploadPolicy(
    max_files_per_session=2, max_file_bytes=1024 * 1024, max_batch_bytes=1024 * 1024
)


def _use_case(
    repository: InMemoryRepository,
    parser: FakeParser | None = None,
    policy: UploadPolicy = SMALL_POLICY,
) -> IngestDocuments:
    return IngestDocuments(
        repository=repository,
        parser=parser or FakeParser(),
        chunker=FakeChunker(),
        limiter=WorkLimiter(2, "ingestion"),
        session_locks=SessionLocks(),
        policy_provider=lambda: policy,
    )


def _command(*names: str, data: bytes = PDF) -> IngestDocumentsCommand:
    return IngestDocumentsCommand(
        session_id="session-1",
        files=[IncomingFile(name, io.BytesIO(data)) for name in names],
    )


def test_ingests_sections_and_bridges_consecutive_pages(
    repository: InMemoryRepository,
) -> None:
    parser = FakeParser(
        [ParsedSection("first page", {"page": 1}), ParsedSection("second", {"page": 2})]
    )

    result = _use_case(repository, parser).execute(_command("a.pdf"))

    assert result == MessageResponse(message="Successfully ingested a.pdf (3 chunks).")
    bridge = repository.sessions["session-1"][-1]
    assert bridge.text == "first page second"


def test_summarizes_multi_file_batches(repository: InMemoryRepository) -> None:
    result = _use_case(repository).execute(_command("a.pdf", "b.pdf"))

    assert result.message == (
        "Successfully ingested 2 file(s): a.pdf, b.pdf (2 chunks total)."
    )


@pytest.mark.parametrize(
    ("command", "detail"),
    [
        (IngestDocumentsCommand("bad id!", []), "Invalid session_id format"),
        (IngestDocumentsCommand("session-1", []), "No file provided."),
        (_command("a.pdf", "b.pdf", "c.pdf"), "A maximum of 2 files"),
        (_command("a.pdf", "a.pdf"), "Duplicate filenames are not allowed."),
        (_command(""), "Missing filename."),
        (_command("a.pdf", data=b"not a pdf"), "does not match its PDF extension"),
    ],
)
def test_rejects_invalid_batches(
    repository: InMemoryRepository, command: IngestDocumentsCommand, detail: str
) -> None:
    with pytest.raises(InvalidInputError) as error:
        _use_case(repository).execute(command)

    assert detail in str(error.value.detail)


def test_rejects_existing_filenames_and_full_sessions(
    repository: InMemoryRepository,
) -> None:
    use_case = _use_case(repository)
    use_case.execute(_command("a.pdf"))

    with pytest.raises(ConflictError):
        use_case.execute(_command("a.pdf"))
    with pytest.raises(InvalidInputError, match="at most 2 files"):
        use_case.execute(_command("b.pdf", "c.pdf"))


def test_parser_value_errors_become_invalid_input(
    repository: InMemoryRepository,
) -> None:
    class BrokenParser(FakeParser):
        def parse_sections(
            self, file_bytes: bytes, filename: str
        ) -> list[ParsedSection]:
            raise ValueError("OCR page limit exceeded.")

    with pytest.raises(InvalidInputError, match="OCR page limit exceeded"):
        _use_case(repository, BrokenParser()).execute(_command("a.pdf"))


def test_enforces_file_and_batch_byte_limits(repository: InMemoryRepository) -> None:
    tight = UploadPolicy(max_files_per_session=5, max_file_bytes=10, max_batch_bytes=15)

    with pytest.raises(PayloadTooLargeError, match="exceeds the 0MB limit"):
        _use_case(repository, policy=tight).execute(_command("a.pdf", data=PDF * 2))
    with pytest.raises(PayloadTooLargeError, match="upload batch exceeds"):
        _use_case(repository, policy=tight).execute(
            _command("a.pdf", "b.pdf", data=PDF[:9])
        )


def test_concurrent_uploads_recheck_session_duplicates(
    repository: InMemoryRepository,
) -> None:
    """A second upload must observe the first commit before entering ingestion."""
    use_case = _use_case(repository)
    first_entered = Event()
    release_first = Event()

    def slow_ingest(*args: object) -> MessageResponse:
        first_entered.set()
        assert release_first.wait(timeout=5)
        repository.save_nodes(
            FakeChunker().chunk("x", {"filename": "same.pdf"}), "session-1"
        )
        return MessageResponse(message="ingested")

    with (
        patch.object(use_case, "_ingest", side_effect=slow_ingest),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        first = pool.submit(use_case.execute, _command("same.pdf"))
        assert first_entered.wait(timeout=5)
        second = pool.submit(use_case.execute, _command("same.pdf"))
        release_first.set()
        assert first.result(timeout=5).message == "ingested"
        with pytest.raises(ConflictError):
            second.result(timeout=5)
