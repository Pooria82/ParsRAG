"""Defects found in the October 2026 project review, one test each."""

import io
import socket
import threading
import zipfile
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware import ContentLengthLimitMiddleware, configured_hosts
from backend.core.domain.documents import ExtractedNode
from backend.core.domain.enums import ModelProvider
from backend.core.domain.exceptions import (
    ConflictError,
    DocumentError,
    InvalidInputError,
    ModelKeyMissingError,
    UpstreamServiceError,
)
from backend.core.domain.upload_policy import UploadPolicy
from backend.core.dto.input.documents import ReuseDocumentRequest
from backend.core.dto.input.model import ModelConfigurationRequest
from backend.core.dto.output.updates import PublishedRelease
from backend.core.runtime.capacity import WorkLimiter
from backend.core.runtime.session_locks import SessionLocks
from backend.core.use_case.ingestion.file_validation import validate_upload
from backend.core.use_case.model.configure_model import ConfigureModel
from backend.core.use_case.session.delete_session import DeleteSession
from backend.core.use_case.session.reuse_document import ReuseDocument
from backend.core.use_case.system.check_for_updates import CheckForUpdates
from backend.infrastructure.llm import factory
from backend.infrastructure.llm.gateway import LlamaIndexModelGateway
from backend.infrastructure.parsers.document_parser import parse_document_file
from backend.tests.core.use_case.fakes import InMemoryRepository


def test_allowed_hosts_add_to_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """The container health check and the update script use 127.0.0.1."""
    monkeypatch.setenv("PARSRAG_ALLOWED_HOSTS", "192.168.1.20, parsrag.lan")
    assert configured_hosts() == [
        "localhost",
        "127.0.0.1",
        "::1",
        "192.168.1.20",
        "parsrag.lan",
    ]


def _api(base_url: str) -> ModelConfigurationRequest:
    return ModelConfigurationRequest(
        provider=ModelProvider.API,
        model_name="m",
        base_url=base_url,
        disclosure_acknowledged=True,
    )


def test_the_status_check_only_sends_the_key_of_its_own_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(factory, "_api_key", "openrouter-key")
    monkeypatch.setattr(
        factory,
        "_api_keys",
        {factory._origin("https://openrouter.ai/v1"): "openrouter-key"},
    )
    monkeypatch.setattr(factory, "model_api_is_external", lambda url: True)
    monkeypatch.setattr(factory, "_status_cache", None)
    monkeypatch.setattr(
        factory, "_configuration", _api("https://api.groq.com/openai/v1")
    )
    client = MagicMock()
    with patch.object(factory, "guarded_http_client", return_value=client):
        assert factory.model_connection_status().status == "key_missing"
    client.__enter__.return_value.get.assert_not_called()
    assert factory.get_model_configuration().api_key_configured is False


def test_a_saved_api_connection_starts_without_dns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Offline at start, the app still becomes ready; requests are checked later."""
    monkeypatch.setattr(factory, "_api_keys", {})
    with (
        patch(
            "backend.infrastructure.llm.endpoint_policy.socket.getaddrinfo",
            side_effect=socket.gaierror("offline"),
        ),
        patch.object(factory, "save_model_configuration"),
        patch.object(factory, "Settings"),
    ):
        result = factory.configure_model(
            _api("https://openrouter.ai/api/v1"), verify=False, persist=False
        )
    assert result.base_url == "https://openrouter.ai/api/v1"


def test_a_keyless_api_that_does_not_resolve_is_unreachable_not_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unresolved(url: str) -> bool:
        raise ValueError("The model API hostname could not be resolved.")

    monkeypatch.setattr(factory, "model_api_is_external", unresolved)
    assert factory._check_connection(_api("http://vllm:8000/v1"), None) == "unreachable"


def test_saving_without_a_key_returns_its_own_code() -> None:
    gateway = MagicMock()
    gateway.configure.side_effect = ModelKeyMissingError(
        "No API key for openrouter.ai."
    )
    with pytest.raises(InvalidInputError) as raised:
        ConfigureModel(gateway).execute(_api("https://openrouter.ai/api/v1"))
    assert raised.value.code == "api_key_missing"


def test_a_malformed_csv_is_a_corrupt_file() -> None:
    data = b'name,notes\nAli,"' + b"x" * 200_000 + b"\n"
    with pytest.raises(DocumentError) as raised:
        parse_document_file(data, "notes.csv")
    assert raised.value.code == "corrupt_file"


def test_an_empty_title_is_an_upstream_failure() -> None:
    with (
        patch.object(
            factory, "generate_conversation_title", side_effect=ValueError("empty")
        ),
        pytest.raises(UpstreamServiceError),
    ):
        LlamaIndexModelGateway().generate_title("سلام", "fa")


def test_word_online_documents_with_document2_xml_are_accepted() -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("_rels/.rels", "<Relationships/>")
        archive.writestr("word/document2.xml", "<w:document/>")
    validate_upload("online.docx", output.getvalue())


def test_an_oversized_body_carries_the_too_large_code() -> None:
    app = FastAPI()

    @app.post("/echo")
    def echo() -> dict[str, str]:
        return {}

    app.add_middleware(ContentLengthLimitMiddleware, max_bytes=10)
    response = TestClient(app).post("/echo", content=b"x" * 100)
    assert response.status_code == 413
    assert response.json()["code"] == "too_large"


def test_a_malformed_session_id_is_invalid_session() -> None:
    with pytest.raises(InvalidInputError) as raised:
        DeleteSession(InMemoryRepository(), SessionLocks()).execute("bad.id")
    assert raised.value.code == "invalid_session"


class SlowFeed:
    """A release feed that answers only when allowed to."""

    def __init__(self) -> None:
        """Start blocked."""
        self.release = threading.Event()
        self.calls = 0

    def releases(self) -> list[PublishedRelease]:
        """Wait for the test, like a slow GitHub."""
        self.calls += 1
        self.release.wait(5)
        return [PublishedRelease(version="9.0.0", url="")]

    def notes(self, version: str, language: Literal["fa", "en"]) -> str | None:
        """No notes."""
        return None


def test_a_slow_update_check_does_not_block_other_requests() -> None:
    feed = SlowFeed()
    checker = CheckForUpdates(feed, "1.0.0", lambda: True, lambda: 0.0)
    first = threading.Thread(target=checker.execute)
    first.start()
    while feed.calls == 0:
        threading.Event().wait(0.01)
    # A second request returns at once with what is known, without a new call.
    assert checker.execute().update_available is False
    assert feed.calls == 1
    feed.release.set()
    first.join(5)
    assert checker.execute().latest_version == "9.0.0"


def test_reusing_a_document_with_the_same_content_is_refused() -> None:
    repository = InMemoryRepository()
    repository.save_nodes(
        [
            ExtractedNode(
                text="a", metadata={"filename": "a.pdf", "content_sha256": "x"}
            )
        ],
        "target",
    )
    repository.save_nodes(
        [
            ExtractedNode(
                text="a", metadata={"filename": "b.pdf", "content_sha256": "x"}
            )
        ],
        "source",
    )
    policy = UploadPolicy(max_files_per_session=10, max_file_bytes=1, max_batch_bytes=1)
    reuse = ReuseDocument(
        repository, WorkLimiter(1, "ingestion"), SessionLocks(), lambda: policy
    )
    with pytest.raises(ConflictError) as raised:
        reuse.execute(
            "target", ReuseDocumentRequest(source_session_id="source", filename="b.pdf")
        )
    assert raised.value.code == "duplicate_content"


def test_the_request_ceiling_follows_the_env_batch_limit_not_an_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.api import dependencies

    mebibyte = 1024 * 1024
    monkeypatch.delenv("PARSRAG_MAX_REQUEST_BYTES", raising=False)
    # A lower batch limit saved in the app is active...
    monkeypatch.setenv("PARSRAG_MAX_BATCH_BYTES", str(100 * mebibyte))
    # ...but .env said 500 MiB, so the ceiling stays where .env put it.
    monkeypatch.setattr(
        dependencies.runtime_settings_store,
        "env_values",
        lambda: {"PARSRAG_MAX_BATCH_BYTES": str(500 * mebibyte)},
    )
    assert dependencies.max_request_bytes() == 510 * mebibyte
