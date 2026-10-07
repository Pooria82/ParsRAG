"""HTTP driving adapter: translate requests into use-case calls.

Routes own transport concerns only (parameter binding, readiness gating, and
response codes). Business rules live in ``backend.core.use_case`` and errors
are mapped centrally by ``backend.api.errors``.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse

from backend.api.dependencies import (
    get_answer_query,
    get_check_readiness,
    get_configure_model,
    get_delete_document,
    get_delete_session,
    get_describe_capabilities,
    get_generate_conversation_title,
    get_ingest_documents,
    get_list_ollama_models,
    get_list_session_files,
    get_read_model_configuration,
    get_read_query_progress,
    get_reuse_document,
    require_runtime_ready,
)
from backend.core.dto.input.documents import DeleteDocumentRequest, ReuseDocumentRequest
from backend.core.dto.input.ingestion import IncomingFile, IngestDocumentsCommand
from backend.core.dto.input.model import (
    ConversationTitleRequest,
    ModelConfigurationRequest,
)
from backend.core.dto.input.query import QueryRequest
from backend.core.dto.output.capabilities import AppCapabilitiesResponse
from backend.core.dto.output.common import MessageResponse, StatusResponse
from backend.core.dto.output.documents import ReusedDocumentResponse
from backend.core.dto.output.ingestion import IngestResponse
from backend.core.dto.output.model import (
    ConversationTitleResponse,
    ModelConfigurationResponse,
    OllamaModel,
)
from backend.core.dto.output.query import QueryProgressResponse, QueryResponse
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

router = APIRouter()


@router.get("/health", response_model=StatusResponse)
@router.get("/health/live", response_model=StatusResponse)
def health_check() -> StatusResponse:
    """Report process liveness without waiting for model initialization."""
    return StatusResponse(status="ok")


@router.get("/health/ready", response_model=StatusResponse)
def readiness_check(
    use_case: CheckReadiness = Depends(get_check_readiness),  # noqa: B008
) -> StatusResponse | JSONResponse:
    """Report model initialization and live vector-store availability."""
    status = use_case.execute()
    if status == "ready":
        return StatusResponse(status=status)
    return JSONResponse(status_code=503, content={"status": status})


@router.get("/capabilities", response_model=AppCapabilitiesResponse)
def read_capabilities(
    use_case: DescribeCapabilities = Depends(get_describe_capabilities),  # noqa: B008
) -> AppCapabilitiesResponse:
    """Return the active ingestion contract for runtime-synchronized clients."""
    return use_case.execute()


@router.get("/models/configuration", response_model=ModelConfigurationResponse)
def read_model_configuration(
    use_case: ReadModelConfiguration = Depends(get_read_model_configuration),  # noqa: B008
) -> ModelConfigurationResponse:
    """Returns the active model connection without exposing secrets."""
    return use_case.execute()


@router.put("/models/configuration", response_model=ModelConfigurationResponse)
def update_model_configuration(
    request: ModelConfigurationRequest,
    use_case: ConfigureModel = Depends(get_configure_model),  # noqa: B008
) -> ModelConfigurationResponse:
    """Applies model settings for subsequent queries."""
    return use_case.execute(request)


@router.post("/conversations/title", response_model=ConversationTitleResponse)
def create_conversation_title(
    request: ConversationTitleRequest,
    _ready: None = Depends(require_runtime_ready),
    use_case: GenerateConversationTitle = Depends(get_generate_conversation_title),  # noqa: B008
) -> ConversationTitleResponse:
    """Generate a bounded title after the first successful conversation turn."""
    return use_case.execute(request)


@router.get("/models/ollama", response_model=list[OllamaModel])
def read_ollama_models(
    base_url: str = "http://localhost:11434",
    use_case: ListOllamaModels = Depends(get_list_ollama_models),  # noqa: B008
) -> list[OllamaModel]:
    """Lists installed models from an Ollama service."""
    return use_case.execute(base_url)


@router.post("/ingest", response_model=IngestResponse)
def ingest_document(
    _ready: None = Depends(require_runtime_ready),
    file: UploadFile | None = File(None),  # noqa: B008
    files: list[UploadFile] | None = File(None),  # noqa: B008
    session_id: str = Form(...),
    use_case: IngestDocuments = Depends(get_ingest_documents),  # noqa: B008
) -> IngestResponse:
    """Ingest a bounded set of supported files into one isolated session."""
    uploads = [*(files or []), *([file] if file else [])]
    command = IngestDocumentsCommand(
        session_id=session_id,
        files=[IncomingFile(upload.filename, upload.file) for upload in uploads],
    )
    return use_case.execute(command)


@router.post("/query", response_model=QueryResponse)
def query_rag(
    request: QueryRequest,
    _ready: None = Depends(require_runtime_ready),
    use_case: AnswerQuery = Depends(get_answer_query),  # noqa: B008
) -> QueryResponse:
    """Processes a query using the specified RAG mode and multi-file options."""
    return use_case.execute(request)


@router.get("/queries/{request_id}/progress", response_model=QueryProgressResponse)
def read_query_progress(
    request_id: UUID,
    use_case: ReadQueryProgress = Depends(get_read_query_progress),  # noqa: B008
) -> QueryProgressResponse:
    """Return a query's coarse stage without prompts, answers, or document data."""
    return use_case.execute(request_id)


@router.get("/sessions/{session_id}/files", response_model=list[str])
def get_session_files(
    session_id: str,
    use_case: ListSessionFiles = Depends(get_list_session_files),  # noqa: B008
) -> list[str]:
    """Retrieves all distinct filenames indexed for a given session."""
    return use_case.execute(session_id)


@router.post(
    "/sessions/{session_id}/files/reuse", response_model=ReusedDocumentResponse
)
def reuse_session_document(
    session_id: str,
    request: ReuseDocumentRequest,
    use_case: ReuseDocument = Depends(get_reuse_document),  # noqa: B008
) -> ReusedDocumentResponse:
    """Reuse a prior session's indexed vectors without storing raw upload bytes."""
    return use_case.execute(session_id, request)


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
def delete_session(
    session_id: str,
    use_case: DeleteSession = Depends(get_delete_session),  # noqa: B008
) -> MessageResponse:
    """Deletes all indexed vectors and documents for a given session."""
    return use_case.execute(session_id)


@router.delete("/sessions/{session_id}/files", response_model=MessageResponse)
def delete_session_document(
    session_id: str,
    request: DeleteDocumentRequest,
    use_case: DeleteDocument = Depends(get_delete_document),  # noqa: B008
) -> MessageResponse:
    """Deletes one indexed document without affecting the rest of the session."""
    return use_case.execute(session_id, request)
