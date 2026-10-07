"""Fixtures shared by framework-free use-case tests."""

import pytest

from backend.tests.core.use_case.fakes import InMemoryRepository


@pytest.fixture
def repository() -> InMemoryRepository:
    """Provide an empty in-memory repository."""
    return InMemoryRepository()
