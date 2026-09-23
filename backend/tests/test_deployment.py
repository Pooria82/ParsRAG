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
    assert '"${PARSRAG_BIND_HOST:-127.0.0.1}:${PARSRAG_PORT:-8000}:8000"' in compose
    assert '"6333:6333"' not in compose
    assert '"11434:11434"' not in compose
    assert "qdrant_data:/qdrant/storage" in compose
    assert "ollama_models:/root/.ollama" in compose
    assert "model_cache:/home/parsrag/.cache" in compose
    assert "app_config:/var/lib/parsrag" in compose
    assert 'profiles: ["local-model"]' in compose
    assert 'HF_HUB_DISABLE_XET: "${HF_HUB_DISABLE_XET:-1}"' in compose
    assert "parsrag_backend:" in compose
    assert "parsrag_egress:" in compose
    assert "internal: true" in compose
    assert (
        'PARSRAG_MAX_FILES_PER_SESSION: "${PARSRAG_MAX_FILES_PER_SESSION:-10}"'
        in compose
    )
    assert 'OLLAMA_MAX_LOADED_MODELS: "${OLLAMA_MAX_LOADED_MODELS:-1}"' in compose
    assert 'mem_limit: "${PARSRAG_APP_MEMORY_LIMIT:-6g}"' in compose

    ollama_service = compose.split("\n  ollama:\n", maxsplit=1)[1].split(
        "\n  ollama-init:\n", maxsplit=1
    )[0]
    assert "- parsrag_backend" in ollama_service
    assert "- parsrag_egress" in ollama_service


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
    assert "OCR_MAX_IMAGES=30" in example
    assert "PARSRAG_MAX_FILES_PER_SESSION=10" in example
    assert "PARSRAG_MAX_FILE_BYTES=104857600" in example


def test_gpu_override_accelerates_embeddings_and_ollama() -> None:
    """The optional NVIDIA overlay grants both model services GPU access."""
    gpu = (ROOT / "compose.gpu.yaml").read_text(encoding="utf-8")

    assert "download.pytorch.org/whl/cu124" in gpu
    assert "EMBED_DEVICE: cuda" in gpu
    assert gpu.count("driver: nvidia") == 2
    assert gpu.count("capabilities: [gpu]") == 2


def test_low_vram_override_prioritizes_ollama_generation() -> None:
    """Small NVIDIA cards can keep embeddings off VRAM to avoid model spill."""
    overlay = (ROOT / "compose.gpu-low-vram.yaml").read_text(encoding="utf-8")

    assert "EMBED_DEVICE: cpu" in overlay
    assert 'OLLAMA_CONTEXT_LENGTH: "${OLLAMA_LOW_VRAM_CONTEXT_LENGTH:-2048}"' in overlay
    assert 'LLAMA_ARG_FIT_TARGET: "${OLLAMA_LOW_VRAM_FIT_TARGET:-0}"' in overlay


def test_amd_override_uses_rocm_for_embeddings_and_ollama() -> None:
    """Linux AMD hosts receive ROCm wheels and GPU device mappings."""
    gpu = (ROOT / "compose.amd.yaml").read_text(encoding="utf-8")

    assert "download.pytorch.org/whl/rocm6.2" in gpu
    assert "ollama/ollama:rocm" in gpu
    assert gpu.count("/dev/kfd:/dev/kfd") == 2
    assert gpu.count("/dev/dri:/dev/dri") == 2


def test_vite_development_proxy_covers_every_backend_route_family() -> None:
    """Local hot reload forwards every API route used by the workspace."""
    config = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")

    for route in (
        "/health",
        "/capabilities",
        "/ingest",
        "/query",
        "/queries",
        "/sessions",
        "/models",
        "/conversations",
    ):
        assert f"'{route}': 'http://localhost:8000'" in config
    assert "codeSplitting" in config
    assert "maxSize: 250_000" in config


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
