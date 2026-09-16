import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from llama_index.core.llms import ChatMessage as LlamaChatMessage

from backend.api.dependencies import get_document_repository, get_query_strategy
from backend.core.condenser import CondenseQuestionPipeline
from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import QueryRequest, QueryResponse
from backend.infrastructure.parsers.chunker import chunk_text
from backend.infrastructure.parsers.document_parser import parse_document

router = APIRouter()

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_FILES_PER_BATCH = 5
SESSION_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


@router.get("/health")
def health_check() -> dict[str, str]:
    """Health check endpoint to verify backend service readiness."""
    return {"status": "ok"}


@router.post("/ingest")
def ingest_document(
    file: UploadFile | None = File(None),  # noqa: B008
    files: list[UploadFile] | None = File(None),  # noqa: B008
    session_id: str | None = Form(None),
    repo: AbstractDocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> dict[str, str]:
    """Ingests 1 to 5 documents, parses them, chunks them, and saves them to Qdrant."""
    # 1. Validate session_id
    if session_id is not None and not SESSION_ID_REGEX.match(session_id):
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

    total_chunks = 0
    ingested_names: list[str] = []

    # 3. Parse, chunk, and save each file
    for upload_item in upload_list:
        if not upload_item.filename:
            raise HTTPException(
                status_code=400,
                detail="Missing filename.",
            )

        file_bytes = upload_item.file.read()
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{upload_item.filename}' exceeds the 50MB limit.",
            )

        try:
            text = parse_document(file_bytes, upload_item.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        metadata = {"filename": upload_item.filename}
        nodes = chunk_text(text, metadata=metadata)
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
    repo: AbstractDocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> QueryResponse:
    """Processes a query using the specified RAG mode and multi-file options."""
    # Map chat messages for LlamaIndex compatibility
    llama_chat_history = [
        LlamaChatMessage(role=msg.role, content=msg.content)
        for msg in request.chat_history
    ]

    # 1. Condense the question (conversational memory)
    condenser = CondenseQuestionPipeline()
    condensed_query = condenser.condense(request.prompt, llama_chat_history)

    # 2. Get the strategy based on the mode
    strategy = get_query_strategy(request.mode, repo=repo)

    # 3. Execute strategy
    response = strategy.execute(
        query=condensed_query,
        chat_history=llama_chat_history,
        session_id=request.session_id,
        top_k=request.top_k,
        file_filter=request.file_filter,
    )

    return response


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
