import json

import pytest

from backend.core.models.domain import ModelConfigurationRequest, ModelProvider
from backend.infrastructure.llm.config_store import (
    load_model_configuration,
    save_model_configuration,
)


def test_model_configuration_persists_without_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only restart-safe, non-secret connection fields are persisted."""
    from pathlib import Path

    path = Path("scratch/test-model-configuration.json")
    path.unlink(missing_ok=True)
    monkeypatch.setenv("PARSRAG_CONFIG_PATH", str(path))
    configuration = ModelConfigurationRequest(
        provider=ModelProvider.API,
        model_name="corporate-model",
        base_url="https://models.example/v1",
        api_key="do-not-write-me",
        disclosure_acknowledged=True,
    )

    try:
        save_model_configuration(configuration)

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "api_key" not in payload
        assert payload["disclosure_acknowledged"] is True
        assert load_model_configuration() == configuration.model_copy(
            update={"api_key": None}
        )
    finally:
        path.unlink(missing_ok=True)
