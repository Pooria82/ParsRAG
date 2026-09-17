"""Deterministic checks for production packaging and orchestration."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.api.dependencies import get_document_repository

ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_builds_frontend_and_runs_as_non_root() -> None:
    """The application image contains the active UI and a restricted runtime."""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM node:22-bookworm-slim AS frontend-build" in dockerfile
    assert "npm ci" in dockerfile and "npm run build" in dockerfile
    assert "requirements-runtime.txt" in dockerfile
    assert "download.pytorch.org/whl/cpu" in dockerfile
    assert "COPY requirements.txt" not in dockerfile
    assert "tesseract-ocr-fas" in dockerfile
    assert "USER parsrag" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "frontend/dist" in dockerfile


def test_compose_keeps_infrastructure_private_and_persistent() -> None:
    """Compose publishes only the app while persisting model and vector data."""
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")

    for service in ("app:", "qdrant:", "ollama:", "ollama-init:"):
        assert service in compose
    assert '"${PARSRAG_PORT:-8000}:8000"' in compose
    assert '"6333:6333"' not in compose
    assert '"11434:11434"' not in compose
    assert "qdrant_data:/qdrant/storage" in compose
    assert "ollama_models:/root/.ollama" in compose
    assert "model_cache:/home/parsrag/.cache" in compose
    assert 'HF_HUB_DISABLE_XET: "${HF_HUB_DISABLE_XET:-1}"' in compose
    assert "parsrag_backend:" in compose
    assert "parsrag_egress:" in compose
    assert "internal: true" in compose


def test_docker_context_excludes_secrets_and_local_test_data() -> None:
    """Secrets, caches, and user documents cannot enter the build context."""
    patterns = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    for expected in (".env", ".venv", "testData", "scratch", "data"):
        assert expected in patterns


def test_example_environment_contains_no_example_secret() -> None:
    """The committed environment template documents keys without credentials."""
    example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "OPENROUTER_API_KEY=\n" in example
    assert "sk-or-" not in example
    assert "OCR_MAX_PAGES=30" in example


@patch("backend.api.dependencies.QdrantRepository")
def test_repository_uses_container_environment(
    mock_repository: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The repository adapter resolves its host and port at the composition root."""
    monkeypatch.setenv("QDRANT_HOST", "qdrant")
    monkeypatch.setenv("QDRANT_PORT", "7333")

    dependency = get_document_repository()
    assert next(dependency) is mock_repository.return_value
    dependency.close()
    mock_repository.assert_called_once_with(host="qdrant", port=7333)
