"""Persistent non-secret model configuration storage."""

from __future__ import annotations

import json
import os
from pathlib import Path

from backend.core.models.domain import ModelConfigurationRequest


def model_configuration_path() -> Path:
    """Return the configured local path for non-secret model settings."""
    return Path(os.getenv("PARSRAG_CONFIG_PATH", "data/model-configuration.json"))


def load_model_configuration() -> ModelConfigurationRequest | None:
    """Load persisted model settings while ignoring absent or malformed state."""
    path = model_configuration_path()
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        configuration = ModelConfigurationRequest.model_validate(payload)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return configuration.model_copy(update={"api_key": None})


def save_model_configuration(configuration: ModelConfigurationRequest) -> None:
    """Atomically persist model settings without writing API credentials."""
    path = model_configuration_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload = configuration.model_dump(mode="json", exclude={"api_key"})
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if os.name != "nt":
        temporary.chmod(0o600)
    os.replace(temporary, path)
