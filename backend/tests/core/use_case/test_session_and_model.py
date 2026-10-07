"""Session lifecycle, model, and system use cases exercised with fakes."""

from typing import Literal
from unittest.mock import MagicMock

import pytest

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.enums import ModelProvider
from backend.core.domain.exceptions import (
    ConflictError,
    InvalidInputError,
    ModelConnectionError,
    NotFoundError,
    UpstreamServiceError,
)
from backend.core.domain.upload_policy import UploadPolicy
from backend.core.dto.input.documents import DeleteDocumentRequest, ReuseDocumentRequest
from backend.core.dto.input.model import (
    ConversationTitleRequest,
    ModelConfigurationRequest,
)
from backend.core.dto.output.model import ModelConfigurationResponse, OllamaModel
from backend.core.runtime.capacity import WorkLimiter
from backend.core.runtime.readiness import RuntimeState
from backend.core.runtime.session_locks import SessionLocks
from backend.core.use_case.model.configure_model import ConfigureModel
from backend.core.use_case.model.generate_conversation_title import (
    GenerateConversationTitle,
)
from backend.core.use_case.model.list_ollama_models import ListOllamaModels
from backend.core.use_case.model.read_model_configuration import (
    ReadModelConfiguration,
)
from backend.core.use_case.session.delete_document import DeleteDocument
from backend.core.use_case.session.delete_session import DeleteSession
from backend.core.use_case.session.list_session_files import ListSessionFiles
from backend.core.use_case.session.reuse_document import ReuseDocument
from backend.core.use_case.system.check_readiness import CheckReadiness
from backend.core.use_case.system.describe_capabilities import DescribeCapabilities
from backend.tests.core.use_case.fakes import InMemoryRepository

CONFIGURATION = ModelConfigurationResponse(
    provider=ModelProvider.OLLAMA,
    model_name="qwen2.5:7b",
    base_url="http://localhost:11434",
    api_key_configured=False,
)


class FakeGateway:
    """``ModelGateway`` fake that can simulate connection failures."""

    def __init__(self, fail: bool = False) -> None:
        """Configure whether calls raise ``ModelConnectionError``."""
        self.fail = fail

    def current_configuration(self) -> ModelConfigurationResponse:
        """Return the fixed configuration."""
        return CONFIGURATION

    def configure(
        self, configuration: ModelConfigurationRequest
    ) -> ModelConfigurationResponse:
        """Accept or reject the connection."""
        if self.fail:
            raise ModelConnectionError("unreachable")
        return CONFIGURATION

    def list_ollama_models(self, base_url: str) -> list[OllamaModel]:
        """List one model or fail."""
        if self.fail:
            raise ModelConnectionError("unreachable")
        return [OllamaModel(name="qwen2.5:7b")]

    def generate_title(self, prompt: str, language: Literal["fa", "en"]) -> str:
        """Echo a short title."""
        return f"{language}: {prompt[:10]}"


def _seed(repository: InMemoryRepository, session_id: str, *names: str) -> None:
    for name in names:
        repository.save_nodes(
            [ExtractedNode(text=name, metadata={"filename": name})], session_id
        )


def _reuse(repository: InMemoryRepository, max_files: int = 10) -> ReuseDocument:
    policy = UploadPolicy(
        max_files_per_session=max_files, max_file_bytes=1, max_batch_bytes=1
    )
    return ReuseDocument(
        repository, WorkLimiter(1, "ingestion"), SessionLocks(), lambda: policy
    )


def test_session_lifecycle(repository: InMemoryRepository) -> None:
    _seed(repository, "s1", "a.pdf", "b.pdf")
    locks = SessionLocks()

    assert ListSessionFiles(repository).execute("s1") == ["a.pdf", "b.pdf"]
    DeleteDocument(repository, locks).execute(
        "s1", DeleteDocumentRequest(filename="a.pdf")
    )
    assert ListSessionFiles(repository).execute("s1") == ["b.pdf"]
    message = DeleteSession(repository, locks).execute("s1")
    assert message.message == "Session 's1' deleted successfully."
    assert ListSessionFiles(repository).execute("s1") == []


@pytest.mark.parametrize("session_id", ["", "bad id", "x" * 65, "trailing\n"])
def test_session_use_cases_reject_malformed_ids(
    repository: InMemoryRepository, session_id: str
) -> None:
    locks = SessionLocks()
    with pytest.raises(InvalidInputError):
        ListSessionFiles(repository).execute(session_id)
    with pytest.raises(InvalidInputError):
        DeleteSession(repository, locks).execute(session_id)
    with pytest.raises(InvalidInputError):
        DeleteDocument(repository, locks).execute(
            session_id, DeleteDocumentRequest(filename="a.pdf")
        )


def test_reuse_copies_vectors_between_sessions(repository: InMemoryRepository) -> None:
    _seed(repository, "source", "a.pdf")

    result = _reuse(repository).execute(
        "target", ReuseDocumentRequest(source_session_id="source", filename="a.pdf")
    )

    assert (result.filename, result.chunks) == ("a.pdf", 1)
    assert repository.get_session_files("target") == ["a.pdf"]


def test_reuse_rejections(repository: InMemoryRepository) -> None:
    _seed(repository, "source", "a.pdf")
    _seed(repository, "target", "a.pdf")
    _seed(repository, "full", "x.pdf")
    request = ReuseDocumentRequest(source_session_id="source", filename="a.pdf")

    with pytest.raises(InvalidInputError, match="Invalid target session"):
        _reuse(repository).execute("source", request)
    with pytest.raises(NotFoundError):
        _reuse(repository).execute(
            "target",
            ReuseDocumentRequest(source_session_id="source", filename="missing.pdf"),
        )
    with pytest.raises(ConflictError):
        _reuse(repository).execute("target", request)
    with pytest.raises(InvalidInputError, match="The target session is full"):
        _reuse(repository, max_files=1).execute("full", request)


def test_reuse_reports_vanished_source(repository: InMemoryRepository) -> None:
    _seed(repository, "source", "a.pdf")
    repository.copy_document = MagicMock(return_value=0)  # type: ignore[method-assign]

    with pytest.raises(NotFoundError):
        _reuse(repository).execute(
            "target", ReuseDocumentRequest(source_session_id="source", filename="a.pdf")
        )


def test_model_use_cases_translate_gateway_failures() -> None:
    request = ModelConfigurationRequest(
        provider=ModelProvider.OLLAMA,
        model_name="qwen2.5:7b",
        base_url="http://localhost:11434",
    )

    assert ReadModelConfiguration(FakeGateway()).execute() == CONFIGURATION
    assert ConfigureModel(FakeGateway()).execute(request) == CONFIGURATION
    assert ListOllamaModels(FakeGateway()).execute("http://localhost:11434")[0].name
    with pytest.raises(InvalidInputError, match="could not be verified or saved"):
        ConfigureModel(FakeGateway(fail=True)).execute(request)
    with pytest.raises(UpstreamServiceError, match="Could not connect to Ollama"):
        ListOllamaModels(FakeGateway(fail=True)).execute("http://localhost:11434")


def test_conversation_title_uses_a_model_slot() -> None:
    use_case = GenerateConversationTitle(FakeGateway(), WorkLimiter(1, "query"))

    title = use_case.execute(
        ConversationTitleRequest(prompt="Budget plan", language="en")
    )

    assert title.title == "en: Budget pla"


def test_readiness_combines_runtime_state_and_store_probe() -> None:
    runtime = RuntimeState()
    repository = MagicMock()

    assert CheckReadiness(runtime, lambda: repository).execute() == "preparing"
    repository.is_ready.assert_not_called()
    runtime.mark_ready()
    repository.is_ready.return_value = False
    assert CheckReadiness(runtime, lambda: repository).execute() == "failed"
    repository.is_ready.return_value = True
    assert CheckReadiness(runtime, lambda: repository).execute() == "ready"


def test_capabilities_reflect_policy_and_ocr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_ENABLED", "true")
    policy = UploadPolicy(max_files_per_session=3, max_file_bytes=5, max_batch_bytes=9)

    capabilities = DescribeCapabilities(lambda: policy).execute().ingestion

    assert capabilities.max_files_per_session == 3
    assert capabilities.max_batch_size_bytes == 9
    assert capabilities.ocr_enabled is True
    assert ".pdf" in capabilities.supported_extensions
