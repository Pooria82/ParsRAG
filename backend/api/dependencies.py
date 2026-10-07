"""Composition root: wire driven adapters into use cases for FastAPI routes.

This is the only module that knows both the core's ports and the concrete
adapters. Routes receive ready-made use cases through ``Depends`` so tests can
override any collaborator without patching route internals.
"""

import os
from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends, HTTPException

from backend.core.domain.enums import QueryMode
from backend.core.port.document_repository import DocumentRepository
from backend.core.port.query_strategy import QueryStrategy
from backend.core.runtime.capacity import WorkLimiter
from backend.core.runtime.query_progress import query_progress
from backend.core.runtime.readiness import runtime_state
from backend.core.runtime.session_locks import SessionLocks
from backend.core.service.condenser import CondenseQuestionPipeline
from backend.core.strategies.hybrid_rag import HybridRAGStrategy
from backend.core.strategies.llm_only import LLMOnlyStrategy
from backend.core.strategies.strict_rag import StrictRAGStrategy
from backend.core.use_case.ingestion.ingest_documents import IngestDocuments
from backend.core.use_case.model.configure_model import ConfigureModel
from backend.core.use_case.model.generate_conversation_title import (
    GenerateConversationTitle,
)
from backend.core.use_case.model.list_ollama_models import ListOllamaModels
from backend.core.use_case.model.read_model_configuration import (
    ReadModelConfiguration,
)
from backend.core.use_case.query.answer_query import AnswerQuery
from backend.core.use_case.query.read_query_progress import ReadQueryProgress
from backend.core.use_case.session.delete_document import DeleteDocument
from backend.core.use_case.session.delete_session import DeleteSession
from backend.core.use_case.session.list_session_files import ListSessionFiles
from backend.core.use_case.session.reuse_document import ReuseDocument
from backend.core.use_case.system.check_readiness import CheckReadiness
from backend.core.use_case.system.describe_capabilities import DescribeCapabilities
from backend.infrastructure.database.qdrant_repo import QdrantRepository
from backend.infrastructure.llm.gateway import LlamaIndexModelGateway
from backend.infrastructure.parsers.chunker import SentenceWindowChunker
from backend.infrastructure.parsers.document_parser import LocalDocumentParser

ingest_limiter = WorkLimiter(
    int(os.getenv("PARSRAG_INGEST_CONCURRENCY", "1")), "ingestion"
)
query_limiter = WorkLimiter(int(os.getenv("PARSRAG_QUERY_CONCURRENCY", "2")), "query")
session_locks = SessionLocks()
model_gateway = LlamaIndexModelGateway()


@lru_cache(maxsize=1)
def _shared_document_repository() -> DocumentRepository:
    """Create the process-wide repository and reuse its pooled client."""
    host = os.getenv("QDRANT_HOST", "localhost")
    try:
        port = int(os.getenv("QDRANT_PORT", "6333"))
    except ValueError:
        port = 6333
    return QdrantRepository(host=host, port=port)


def get_document_repository() -> Generator[DocumentRepository, None, None]:
    """Provide the shared document repository to FastAPI routes."""
    yield _shared_document_repository()


def get_query_strategy(
    mode: QueryMode, repo: DocumentRepository | None = None
) -> QueryStrategy:
    """Select the strategy implementing the requested query mode.

    Args:
        mode (QueryMode): The execution mode requested by the user.
        repo (DocumentRepository | None, optional): The injected repository;
            defaults to the shared pooled repository.

    Returns:
        QueryStrategy: The instantiated concrete strategy.
    """
    if mode is QueryMode.LLM_ONLY:
        return LLMOnlyStrategy()
    active_repo = repo if repo is not None else _shared_document_repository()
    if mode is QueryMode.STRICT:
        return StrictRAGStrategy(active_repo)
    return HybridRAGStrategy(active_repo)


def require_runtime_ready() -> None:
    """Reject model work while adapters are preparing or unavailable."""
    if not runtime_state.is_ready():
        raise HTTPException(status_code=503, detail={"status": runtime_state.status()})


def get_ingest_documents(
    repo: DocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> IngestDocuments:
    """Build the ingestion use case with local parsing and chunking adapters."""
    return IngestDocuments(
        repository=repo,
        parser=LocalDocumentParser(),
        chunker=SentenceWindowChunker(),
        limiter=ingest_limiter,
        session_locks=session_locks,
    )


def get_answer_query(
    repo: DocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> AnswerQuery:
    """Build the query use case; model-bound collaborators are created lazily."""
    return AnswerQuery(
        repository=repo,
        condenser_factory=lambda: CondenseQuestionPipeline(),
        strategy_resolver=lambda mode: get_query_strategy(mode, repo=repo),
        progress=query_progress,
        limiter=query_limiter,
    )


def get_read_query_progress() -> ReadQueryProgress:
    """Build the query-progress use case."""
    return ReadQueryProgress(query_progress)


def get_list_session_files(
    repo: DocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> ListSessionFiles:
    """Build the session file listing use case."""
    return ListSessionFiles(repo)


def get_reuse_document(
    repo: DocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> ReuseDocument:
    """Build the cross-session document reuse use case."""
    return ReuseDocument(repo, ingest_limiter, session_locks)


def get_delete_session(
    repo: DocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> DeleteSession:
    """Build the session deletion use case."""
    return DeleteSession(repo, session_locks)


def get_delete_document(
    repo: DocumentRepository = Depends(get_document_repository),  # noqa: B008
) -> DeleteDocument:
    """Build the single-document deletion use case."""
    return DeleteDocument(repo, session_locks)


def get_read_model_configuration() -> ReadModelConfiguration:
    """Build the model configuration read use case."""
    return ReadModelConfiguration(model_gateway)


def get_configure_model() -> ConfigureModel:
    """Build the model configuration update use case."""
    return ConfigureModel(model_gateway)


def get_list_ollama_models() -> ListOllamaModels:
    """Build the Ollama model listing use case."""
    return ListOllamaModels(model_gateway)


def get_generate_conversation_title() -> GenerateConversationTitle:
    """Build the conversation title use case sharing the query limiter."""
    return GenerateConversationTitle(model_gateway, query_limiter)


def get_describe_capabilities() -> DescribeCapabilities:
    """Build the capability discovery use case."""
    return DescribeCapabilities()


def get_check_readiness() -> CheckReadiness:
    """Build the readiness use case around the shared repository."""
    return CheckReadiness(runtime_state, lambda: _shared_document_repository())
