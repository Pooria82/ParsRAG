"""Use case: validate, parse, chunk, and index a bounded batch of documents."""

import io
import logging
from collections.abc import Callable
from typing import BinaryIO

from backend.core.domain.documents import ExtractedNode, ParsedSection
from backend.core.domain.exceptions import (
    ConflictError,
    DocumentError,
    InvalidInputError,
    PayloadTooLargeError,
)
from backend.core.domain.session import INVALID_SESSION_ID_MESSAGE, is_valid_session_id
from backend.core.domain.upload_policy import UploadPolicy
from backend.core.dto.input.ingestion import IncomingFile, IngestDocumentsCommand
from backend.core.dto.output.ingestion import IngestedFile, IngestResponse
from backend.core.port.document_parser import DocumentParser
from backend.core.port.document_repository import DocumentRepository
from backend.core.port.text_chunker import TextChunker
from backend.core.runtime.capacity import WorkLimiter
from backend.core.runtime.correlation import current_correlation_id
from backend.core.runtime.session_locks import SessionLocks
from backend.core.service.text_normalization import normalize_persian
from backend.core.use_case.ingestion.file_validation import validate_upload

READ_CHUNK_BYTES = 1024 * 1024
logger = logging.getLogger("parsrag.operations")


def read_bounded(
    stream: BinaryIO, filename: str, remaining_batch_bytes: int, policy: UploadPolicy
) -> bytes:
    """Read one upload in chunks while enforcing file and batch limits.

    Raises:
        PayloadTooLargeError: The file or the remaining batch budget is exceeded.
    """
    buffer = io.BytesIO()
    size = 0
    while chunk := stream.read(READ_CHUNK_BYTES):
        size += len(chunk)
        if size > policy.max_file_bytes:
            limit_mb = policy.max_file_bytes // 1024 // 1024
            raise PayloadTooLargeError(
                f"File '{filename}' exceeds the {limit_mb}MB limit.",
                code="file_too_large",
            )
        if size > remaining_batch_bytes:
            raise PayloadTooLargeError(
                "The upload batch exceeds the configured "
                f"{policy.max_batch_bytes // 1024 // 1024}MB limit.",
                code="batch_too_large",
            )
        buffer.write(chunk)
    return buffer.getvalue()


class IngestDocuments:
    """Index uploaded files into one isolated session.

    The batch is validated as a whole before the session lock is taken, then
    each file is read within its byte budget, signature-checked, parsed into
    sections, chunked with page-boundary bridges, and saved per section so
    memory stays bounded by one section rather than one document.
    """

    def __init__(
        self,
        repository: DocumentRepository,
        parser: DocumentParser,
        chunker: TextChunker,
        limiter: WorkLimiter,
        session_locks: SessionLocks,
        policy_provider: Callable[[], UploadPolicy] = UploadPolicy.from_environment,
    ) -> None:
        """Bind the ports and runtime controls this use case orchestrates."""
        self._repository = repository
        self._parser = parser
        self._chunker = chunker
        self._limiter = limiter
        self._session_locks = session_locks
        self._policy_provider = policy_provider

    def execute(self, command: IngestDocumentsCommand) -> IngestResponse:
        """Ingest the batch and summarize how many chunks were indexed.

        Raises:
            InvalidInputError: The session, filenames, or file contents are invalid.
            ConflictError: A filename already exists in the session.
            PayloadTooLargeError: A file or the batch exceeds the byte limits.
            CapacityExceededError: Every ingestion slot is busy.
            EmptyDocumentError: A document has no extractable text.
        """
        if not is_valid_session_id(command.session_id):
            raise InvalidInputError(INVALID_SESSION_ID_MESSAGE, code="invalid_session")
        if not command.files:
            raise InvalidInputError("No file provided.", code="no_file")
        policy = self._policy_provider()
        if len(command.files) > policy.max_files_per_session:
            raise InvalidInputError(
                f"A maximum of {policy.max_files_per_session} files can be uploaded "
                "per request.",
                code="too_many_files",
            )
        incoming_names = [item.filename or "" for item in command.files]
        if len(set(incoming_names)) != len(incoming_names):
            raise InvalidInputError(
                "Duplicate filenames are not allowed.", code="duplicate_file"
            )

        with self._limiter.slot(), self._session_locks.hold(command.session_id):
            existing_names = set(self._repository.get_session_files(command.session_id))
            duplicates = existing_names.intersection(incoming_names)
            if duplicates:
                raise ConflictError(
                    f"The session already contains: {', '.join(sorted(duplicates))}.",
                    code="duplicate_file",
                )
            if len(existing_names) + len(incoming_names) > policy.max_files_per_session:
                raise InvalidInputError(
                    f"A session can contain at most {policy.max_files_per_session} files.",
                    code="too_many_files",
                )
            logger.info(
                "ingest_started correlation_id=%s file_count=%d",
                current_correlation_id(),
                len(incoming_names),
            )
            return self._ingest(command.files, command.session_id, policy)

    def _ingest(
        self, files: list[IncomingFile], session_id: str, policy: UploadPolicy
    ) -> IngestResponse:
        """Perform bounded parsing, chunking, and persistence for one batch.

        The batch is all-or-nothing: when any file fails, every chunk this
        request stored is deleted, so a failed upload never leaves a partial
        document that looks indexed and blocks a retry with a name conflict.
        """
        total_chunks = 0
        total_bytes = 0
        ingested: list[IngestedFile] = []
        written_names: list[str] = []
        try:
            for item in files:
                if not item.filename:
                    raise InvalidInputError("Missing filename.", code="no_file")
                file_bytes = read_bounded(
                    item.stream,
                    item.filename,
                    policy.max_batch_bytes - total_bytes,
                    policy,
                )
                total_bytes += len(file_bytes)
                try:
                    validate_upload(item.filename, file_bytes)
                    document = self._parser.parse(file_bytes, item.filename)
                except DocumentError as exc:
                    raise InvalidInputError(str(exc), code=exc.code) from exc
                except ValueError as exc:
                    raise InvalidInputError(str(exc), code="invalid_document") from exc
                written_names.append(item.filename)
                chunks = self._index_sections(
                    document.sections, item.filename, session_id
                )
                total_chunks += chunks
                ingested.append(
                    IngestedFile(
                        filename=item.filename,
                        chunks=chunks,
                        sections=len(document.sections),
                        notices=list(document.notices),
                    )
                )
        except BaseException:
            self._roll_back(session_id, written_names)
            raise

        names = [item.filename for item in ingested]
        if len(names) == 1:
            message = f"Successfully ingested {names[0]} ({total_chunks} chunks)."
        else:
            message = (
                f"Successfully ingested {len(names)} file(s): "
                f"{', '.join(names)} ({total_chunks} chunks total)."
            )
        return IngestResponse(message=message, files=ingested)

    def _roll_back(self, session_id: str, filenames: list[str]) -> None:
        """Delete chunks stored by a failed batch, keeping the original error."""
        for filename in filenames:
            try:
                self._repository.delete_document(session_id, filename)
            except Exception:  # the ingestion error must surface, not this one
                logger.exception(
                    "ingest_rollback_failed correlation_id=%s",
                    current_correlation_id(),
                )
        if filenames:
            logger.warning(
                "ingest_rolled_back correlation_id=%s file_count=%d",
                current_correlation_id(),
                len(filenames),
            )

    def _index_sections(
        self, sections: list[ParsedSection], filename: str, session_id: str
    ) -> int:
        """Chunk and save each section; return the number of stored chunks."""
        stored = 0
        previous: ParsedSection | None = None
        sections = [
            ParsedSection(normalize_persian(section.text), section.metadata)
            for section in sections
        ]
        for section in sections:
            nodes = self._chunker.chunk(
                section.text, {"filename": filename, **section.metadata}
            )
            bridge = self._page_bridge(previous, section, filename)
            if bridge is not None:
                nodes.append(bridge)
            self._repository.save_nodes(nodes, session_id=session_id)
            stored += len(nodes)
            previous = section
        return stored

    def _page_bridge(
        self, previous: ParsedSection | None, current: ParsedSection, filename: str
    ) -> ExtractedNode | None:
        """Keep text that crosses a page boundary retrievable as one chunk."""
        if previous is None:
            return None
        previous_page = previous.metadata.get("page")
        current_page = current.metadata.get("page")
        if not isinstance(previous_page, int) or not isinstance(current_page, int):
            return None
        return self._chunker.bridge(
            previous.text,
            current.text,
            filename=filename,
            previous_page=previous_page,
            current_page=current_page,
        )
