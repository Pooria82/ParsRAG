"""Runtime controls and HTTP error mapping that the use cases rely on."""

from unittest.mock import patch

import httpx
import pytest

from backend.api.errors import status_for
from backend.core.domain.enums import ModelProvider
from backend.core.domain.exceptions import (
    ApplicationError,
    CapacityExceededError,
    ConflictError,
    InvalidInputError,
    ModelConnectionError,
    NotFoundError,
    PayloadTooLargeError,
    UpstreamServiceError,
)
from backend.core.dto.input.model import ModelConfigurationRequest
from backend.core.runtime.query_progress import InMemoryQueryProgress
from backend.core.runtime.session_locks import SessionLocks
from backend.infrastructure.llm.gateway import LlamaIndexModelGateway


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (InvalidInputError("x"), 400),
        (NotFoundError("x"), 404),
        (ConflictError("x"), 409),
        (PayloadTooLargeError("x"), 413),
        (CapacityExceededError("x"), 429),
        (UpstreamServiceError("x"), 502),
        (ApplicationError("x"), 400),
    ],
)
def test_application_errors_map_to_http_status(
    error: ApplicationError, status: int
) -> None:
    assert status_for(error) == status


def test_progress_entries_expire() -> None:
    progress = InMemoryQueryProgress(ttl_seconds=-1)

    progress.set_stage("request", "retrieving")

    assert progress.get_stage("request") is None
    assert progress.get_stage("unknown") is None


def test_session_locks_hold_each_stripe_once() -> None:
    locks = SessionLocks(stripes=1)

    with locks.hold("a", "b"):
        assert locks.lock_for("a").locked()
    assert not locks.lock_for("a").locked()


def test_gateway_hides_client_library_failures() -> None:
    gateway = LlamaIndexModelGateway()
    request = ModelConfigurationRequest(
        provider=ModelProvider.OLLAMA, model_name="m", base_url="http://localhost:1"
    )

    with (
        patch(
            "backend.infrastructure.llm.factory.configure_model",
            side_effect=httpx.ConnectError("refused"),
        ),
        pytest.raises(ModelConnectionError),
    ):
        gateway.configure(request)
    with (
        patch(
            "backend.infrastructure.llm.factory.list_ollama_models",
            side_effect=ValueError("blocked"),
        ),
        pytest.raises(ModelConnectionError),
    ):
        gateway.list_ollama_models("http://example.com")
