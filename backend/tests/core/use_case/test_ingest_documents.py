"""Ingestion use-case rules exercised without FastAPI, Qdrant, or parsers."""

import io
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest

from backend.core.domain.documents import ExtractedNode, ParsedDocument, ParsedSection
from backend.core.domain.exceptions import (
    ConflictError,
    DocumentError,
    InvalidInputError,
    PayloadTooLargeError,
    VectorDBConnectionError,
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

    assert result.message == "Successfully ingested a.pdf (3 chunks)."
    assert result.files[0].chunks == 3
    bridge = repository.sessions["session-1"][-1]
    assert bridge.text == "first page second"


class FailingRepository(InMemoryRepository):
    """Store chunks until a configured save call fails."""

    def __init__(self, fail_on_save: int) -> None:
        """Fail on the given 1-based ``save_nodes`` call."""
        super().__init__()
        self.fail_on_save = fail_on_save
        self.saves = 0

    def save_nodes(self, nodes: list[ExtractedNode], session_id: str) -> None:
        """Raise like a dropped Qdrant connection on the configured call."""
        self.saves += 1
        if self.saves == self.fail_on_save:
            raise VectorDBConnectionError("connection reset")
        super().save_nodes(nodes, session_id)


def test_failed_file_is_rolled_back_so_it_can_be_retried() -> None:
    """A failure after some pages were stored leaves no partial document."""
    repository = FailingRepository(fail_on_save=2)
    parser = FakeParser(
        [ParsedSection("first", {"page": 1}), ParsedSection("second", {"page": 2})]
    )
    use_case = _use_case(repository, parser)

    with pytest.raises(VectorDBConnectionError):
        use_case.execute(_command("a.pdf"))

    assert repository.get_session_files("session-1") == []
    repository.fail_on_save = 0
    assert use_case.execute(_command("a.pdf")).message.startswith(
        "Successfully ingested a.pdf"
    )


def test_failed_batch_removes_files_already_stored_by_the_request(
    repository: InMemoryRepository,
) -> None:
    """A later invalid file rolls back earlier files of the same batch only."""
    repository.save_nodes(
        [ExtractedNode(text="kept", metadata={"filename": "old.pdf"})],
        session_id="session-1",
    )
    command = IngestDocumentsCommand(
        session_id="session-1",
        files=[
            IncomingFile("a.pdf", io.BytesIO(PDF)),
            IncomingFile("b.pdf", io.BytesIO(b"not a pdf")),
        ],
    )
    policy = UploadPolicy(
        max_files_per_session=3, max_file_bytes=1024 * 1024, max_batch_bytes=1024**2
    )

    with pytest.raises(InvalidInputError):
        _use_case(repository, policy=policy).execute(command)

    assert repository.get_session_files("session-1") == ["old.pdf"]


def test_rollback_failure_does_not_hide_the_ingestion_error() -> None:
    """The caller sees the original error even when cleanup also fails."""
    repository = FailingRepository(fail_on_save=1)

    def broken_delete(session_id: str, filename: str) -> None:
        raise VectorDBConnectionError("still down")

    repository.delete_document = broken_delete  # type: ignore[method-assign]

    with pytest.raises(VectorDBConnectionError, match="connection reset"):
        _use_case(repository).execute(_command("a.pdf"))


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
        def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
            raise ValueError("Parser failure.")

    with pytest.raises(InvalidInputError, match="Parser failure") as raised:
        _use_case(repository, BrokenParser()).execute(_command("a.pdf"))
    assert raised.value.code == "invalid_document"


def test_document_error_codes_reach_the_caller(
    repository: InMemoryRepository,
) -> None:
    """Encrypted or corrupted files keep their specific reason code."""

    class EncryptedParser(FakeParser):
        def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
            raise DocumentError("The PDF is password-protected.", "encrypted_document")

    with pytest.raises(InvalidInputError) as raised:
        _use_case(repository, EncryptedParser()).execute(_command("a.pdf"))
    assert raised.value.code == "encrypted_document"


def test_response_lists_each_file_with_its_notices(
    repository: InMemoryRepository,
) -> None:
    """Partial OCR is reported per file while the document stays indexed."""
    parser = FakeParser(
        [ParsedSection("one", {"page": 1}), ParsedSection("two", {"page": 3})],
        notices=("ocr_page_limit",),
    )

    result = _use_case(repository, parser).execute(_command("scan.pdf"))

    assert [file.model_dump() for file in result.files] == [
        {
            "filename": "scan.pdf",
            "chunks": 2,
            "sections": 2,
            "notices": ["ocr_page_limit"],
        }
    ]


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
