import io
import os
import re
import zipfile
from pathlib import PurePath
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from llama_index.core.llms import ChatMessage as LlamaChatMessage

from backend.api.dependencies import get_document_repository, get_query_strategy
from backend.core.capacity import WorkLimiter
from backend.core.condenser import CondenseQuestionPipeline
from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import (
    DeleteDocumentRequest,
    ModelConfigurationRequest,
    ModelConfigurationResponse,
    OllamaModel,
    QueryRequest,
    QueryResponse,
)
from backend.core.query_progress import get_query_stage, set_query_stage
from backend.core.runtime import runtime_state
from backend.infrastructure.llm.factory import (
    configure_model,
    get_model_configuration,
    list_ollama_models,
)
from backend.infrastructure.parsers.chunker import chunk_text
from backend.infrastructure.parsers.document_parser import parse_document_sections

router = APIRouter()

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_BATCH_SIZE_BYTES = 100 * 1024 * 1024
MAX_FILES_PER_BATCH = 5
MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_EXPANDED_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE_RATIO = 200
READ_CHUNK_BYTES = 1024 * 1024
SESSION_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_ingest_limiter = WorkLimiter(
    int(os.getenv("PARSRAG_INGEST_CONCURRENCY", "1")), "ingestion"
)
_query_limiter = WorkLimiter(int(os.getenv("PARSRAG_QUERY_CONCURRENCY", "2")), "query")


def _read_bounded(upload: UploadFile, remaining_batch_bytes: int) -> bytes:
    """Read one upload in chunks while enforcing file and batch limits."""
    chunks: list[bytes] = []
    size = 0
    while chunk := upload.file.read(READ_CHUNK_BYTES):
        size += len(chunk)
        if size > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{upload.filename}' exceeds the 50MB limit.",
            )
        if size > remaining_batch_bytes:
            raise HTTPException(
                status_code=413, detail="The upload batch exceeds the 100MB limit."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_archive(data: bytes, extension: str) -> None:
    """Reject forged or explosively expanded Office archives."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise ValueError("The Office archive contains too many entries.")
            expanded = sum(entry.file_size for entry in entries)
            if expanded > MAX_ARCHIVE_EXPANDED_BYTES:
                raise ValueError("The Office archive expands beyond the safe limit.")
            for entry in entries:
                if entry.file_size and entry.compress_size == 0:
                    raise ValueError(
                        "The Office archive has an invalid compression ratio."
                    )
                if (
                    entry.compress_size
                    and entry.file_size / entry.compress_size > MAX_ARCHIVE_RATIO
                ):
                    raise ValueError(
                        "The Office archive has a suspicious compression ratio."
                    )
            names = {entry.filename for entry in entries}
    except zipfile.BadZipFile as exc:
        raise ValueError("The file is not a valid Office document archive.") from exc
    required = "word/document.xml" if extension == ".docx" else "ppt/presentation.xml"
    if "[Content_Types].xml" not in names or required not in names:
        raise ValueError(
            f"The file content does not match its {extension.upper()} extension."
        )


def _validate_file(upload: UploadFile, data: bytes) -> None:
    """Validate filename boundaries and file signatures before parser work."""
    filename = upload.filename or ""
    if (
        len(filename) > 255
        or PurePath(filename).name != filename
        or "/" in filename
        or "\\" in filename
    ):
        raise ValueError("The filename is invalid.")
    extension = PurePath(filename).suffix.lower()
    if extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("The file content does not match its PDF extension.")
        return
    if extension in {".docx", ".pptx"}:
        if not data.startswith(b"PK"):
            raise ValueError("The file content does not match its Office extension.")
        _validate_archive(data, extension)
        return
    raise ValueError("Unsupported file format. Only PDF, DOCX, and PPTX are allowed.")


def require_runtime_ready() -> None:
    """Reject model work while adapters are preparing or unavailable."""
    if not runtime_state.is_ready():
        raise HTTPException(status_code=503, detail={"status": runtime_state.status()})


@router.get("/health")
@router.get("/health/live")
def health_check() -> dict[str, str]:
    """Report process liveness without waiting for model initialization."""
    return {"status": "ok"}


@router.get("/health/ready", response_model=None)
def readiness_check() -> dict[str, str] | JSONResponse:
    """Report model initialization and live vector-store availability."""
    status = runtime_state.status()
    if status == "ready":
        from backend.api.dependencies import _shared_document_repository

        if _shared_document_repository().is_ready():
            return {"status": "ready"}
        status = "failed"
    return JSONResponse(status_code=503, content={"status": status})


@router.get("/models/configuration", response_model=ModelConfigurationResponse)
def read_model_configuration() -> ModelConfigurationResponse:
    """Returns the active model connection without exposing secrets."""
    return get_model_configuration()


@router.put("/models/configuration", response_model=ModelConfigurationResponse)
def update_model_configuration(
    request: ModelConfigurationRequest,
) -> ModelConfigurationResponse:
    """Applies model settings for subsequent queries."""
    try:
        return configure_model(request)
    except (ValueError, TypeError, OSError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=400,
            detail="The model connection could not be verified or saved.",
        ) from exc


@router.get("/models/ollama", response_model=list[OllamaModel])
def read_ollama_models(base_url: str = "http://localhost:11434") -> list[OllamaModel]:
    """Lists installed models from an Ollama service."""
    try:
        return list_ollama_models(base_url)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail="Could not connect to Ollama."
        ) from exc


@router.post("/ingest")
def ingest_document(
    _ready: None = Depends(require_runtime_ready),
    file: UploadFile | None = File(None),  # noqa: B008
    files: list[UploadFile] | None = File(None),  # noqa: B008
    session_id: str = Form(...),
    repo: AbstractDocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> dict[str, str]:
    """Ingests 1 to 5 documents, parses them, chunks them, and saves them to Qdrant."""
    # 1. Validate session_id
    if not SESSION_ID_REGEX.match(session_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid session_id format. Must be 1-64 alphanumeric characters, hyphens, or underscores.",
        )

    # 2. Collect files from either single 'file' or multiple 'files' parameters
    upload_list: list[UploadFile] = []
    if files:
        upload_list.extend(files)
    if file:
        upload_list.append(file)

    if not upload_list:
        raise HTTPException(
            status_code=400,
            detail="No file provided.",
        )

    if len(upload_list) > MAX_FILES_PER_BATCH:
        raise HTTPException(
            status_code=400,
            detail=f"A maximum of {MAX_FILES_PER_BATCH} files can be uploaded per request.",
        )

    with _ingest_limiter.slot():
        return _ingest_documents(upload_list, session_id, repo)


def _ingest_documents(
    upload_list: list[UploadFile],
    session_id: str,
    repo: AbstractDocumentRepository,
) -> dict[str, str]:
    """Perform bounded parsing, chunking, and persistence for one upload batch."""
    total_chunks = 0
    total_bytes = 0
    ingested_names: list[str] = []

    # 3. Parse, chunk, and save each file
    for upload_item in upload_list:
        if not upload_item.filename:
            raise HTTPException(
                status_code=400,
                detail="Missing filename.",
            )

        file_bytes = _read_bounded(upload_item, MAX_BATCH_SIZE_BYTES - total_bytes)
        total_bytes += len(file_bytes)

        try:
            _validate_file(upload_item, file_bytes)
            sections = parse_document_sections(file_bytes, upload_item.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        nodes = []
        for section in sections:
            nodes.extend(
                chunk_text(
                    section.text,
                    metadata={"filename": upload_item.filename, **section.metadata},
                )
            )
        repo.save_nodes(nodes, session_id=session_id)
        total_chunks += len(nodes)
        ingested_names.append(upload_item.filename)

    if len(ingested_names) == 1:
        return {
            "message": f"Successfully ingested {ingested_names[0]} ({total_chunks} chunks)."
        }

    return {
        "message": f"Successfully ingested {len(ingested_names)} file(s): {', '.join(ingested_names)} ({total_chunks} chunks total)."
    }


@router.post("/query", response_model=QueryResponse)
def query_rag(
    request: QueryRequest,
    _ready: None = Depends(require_runtime_ready),
    repo: AbstractDocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> QueryResponse:
    """Processes a query using the specified RAG mode and multi-file options."""
    request_id = str(request.request_id) if request.request_id else None
    try:
        with _query_limiter.slot():
            if request_id:
                set_query_stage(request_id, "understanding")
            llama_chat_history = [
                LlamaChatMessage(role=msg.role, content=msg.content)
                for msg in request.chat_history
            ]
            condenser = CondenseQuestionPipeline()
            condensed_query = condenser.condense(request.prompt, llama_chat_history)
            strategy = get_query_strategy(request.mode, repo=repo)
            if request_id:
                response = strategy.execute(
                    query=condensed_query,
                    chat_history=llama_chat_history,
                    session_id=request.session_id,
                    top_k=request.top_k,
                    file_filter=request.file_filter,
                    progress=lambda stage: set_query_stage(request_id, stage),
                )
            else:
                response = strategy.execute(
                    query=condensed_query,
                    chat_history=llama_chat_history,
                    session_id=request.session_id,
                    top_k=request.top_k,
                    file_filter=request.file_filter,
                )
            if request_id:
                set_query_stage(request_id, "complete")
            return response
    except Exception:
        if request_id:
            set_query_stage(request_id, "failed")
        raise


@router.get("/queries/{request_id}/progress")
def read_query_progress(request_id: UUID) -> dict[str, str]:
    """Return a query's coarse stage without prompts, answers, or document data."""
    stage = get_query_stage(str(request_id))
    if stage is None:
        raise HTTPException(status_code=404, detail="Query progress was not found.")
    return {"stage": stage}


@router.get("/sessions/{session_id}/files", response_model=list[str])
def get_session_files(
    session_id: str,
    repo: AbstractDocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> list[str]:
    """Retrieves all distinct filenames indexed for a given session."""
    if not SESSION_ID_REGEX.match(session_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid session_id format. Must be 1-64 alphanumeric characters, hyphens, or underscores.",
        )
    return repo.get_session_files(session_id)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    repo: AbstractDocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> dict[str, str]:
    """Deletes all indexed vectors and documents for a given session."""
    if not SESSION_ID_REGEX.match(session_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid session_id format. Must be 1-64 alphanumeric characters, hyphens, or underscores.",
        )
    repo.delete_session(session_id)
    return {"message": f"Session '{session_id}' deleted successfully."}


@router.delete("/sessions/{session_id}/files")
def delete_session_document(
    session_id: str,
    request: DeleteDocumentRequest,
    repo: AbstractDocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> dict[str, str]:
    """Deletes one indexed document without affecting the rest of the session."""
    if not SESSION_ID_REGEX.match(session_id):
        raise HTTPException(status_code=400, detail="Invalid session_id format.")
    repo.delete_document(session_id, request.filename)
    return {"message": f"Document '{request.filename}' deleted successfully."}
