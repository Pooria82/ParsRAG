from fastapi import APIRouter, Depends, File, Form, UploadFile
from llama_index.core.llms import ChatMessage as LlamaChatMessage

from backend.api.dependencies import get_document_repository, get_query_strategy
from backend.core.condenser import CondenseQuestionPipeline
from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import QueryRequest, QueryResponse
from backend.infrastructure.parsers.chunker import chunk_text
from backend.infrastructure.parsers.document_parser import parse_document

router = APIRouter()


@router.post("/ingest")
def ingest_document(
    file: UploadFile = File(...),  # noqa: B008
    session_id: str | None = Form(None),
    repo: AbstractDocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> dict[str, str]:
    """Ingests a PDF document, parses it, chunks it, and saves it to the vector database."""
    file_bytes = file.file.read()
    
    # 1. Parse Document
    text = parse_document(file_bytes, file.filename)
    
    # 2. Chunk text
    metadata = {"filename": file.filename}
    nodes = chunk_text(text, metadata=metadata)
    
    # 3. Save to repository
    repo.save_nodes(nodes, session_id=session_id)
    
    return {"message": f"Successfully ingested {file.filename} ({len(nodes)} chunks)."}


@router.post("/query", response_model=QueryResponse)
def query_rag(request: QueryRequest) -> QueryResponse:
    """Processes a query using the specified RAG mode."""
    # Map chat messages for LlamaIndex compatibility
    llama_chat_history = [
        LlamaChatMessage(role=msg.role, content=msg.content)
        for msg in request.chat_history
    ]
    
    # 1. Condense the question (conversational memory)
    condenser = CondenseQuestionPipeline()
    condensed_query = condenser.condense(request.prompt, llama_chat_history)
    
    # 2. Get the strategy based on the mode
    strategy = get_query_strategy(request.mode)
    
    # 3. Execute strategy
    response = strategy.execute(
        query=condensed_query,
        chat_history=llama_chat_history,
        session_id=request.session_id,
    )
    
    return response
