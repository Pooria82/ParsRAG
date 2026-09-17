"""Shared isolation fixtures for API tests."""

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from backend.api.dependencies import get_document_repository
from backend.main import app


@pytest.fixture(autouse=True)
def isolate_document_repository() -> Generator[None, None, None]:
    """Keep route tests independent from a running Qdrant service."""
    app.dependency_overrides[get_document_repository] = lambda: MagicMock()
    try:
        yield
    finally:
        app.dependency_overrides.clear()
