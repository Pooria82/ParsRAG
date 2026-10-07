"""Embedding profiles: E5 prefixes, overrides, and collection versioning."""

import hashlib
from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.embedding_profile import (
    EmbeddingProfile,
    active_embedding_profile,
)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from the default embedding configuration."""
    for name in (
        "EMBED_MODEL_NAME",
        "EMBED_QUERY_PREFIX",
        "EMBED_PASSAGE_PREFIX",
        "EMBED_E5_PREFIXES",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def e5_prefixes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opt in to the documented E5 prefixes."""
    monkeypatch.setenv("EMBED_E5_PREFIXES", "1")


@pytest.mark.parametrize(
    ("model", "query", "passage"),
    [
        ("intfloat/multilingual-e5-base", "query: ", "passage: "),
        ("intfloat/multilingual-e5-large", "query: ", "passage: "),
        ("intfloat/e5-small-v2", "query: ", "passage: "),
        ("intfloat/multilingual-e5-large-instruct", "", ""),
        ("BAAI/bge-m3", "", ""),
    ],
)
@pytest.mark.usefixtures("e5_prefixes")
def test_prefixes_follow_the_model_family(
    monkeypatch: pytest.MonkeyPatch, model: str, query: str, passage: str
) -> None:
    monkeypatch.setenv("EMBED_MODEL_NAME", model)

    profile = active_embedding_profile()

    assert (profile.query_prefix, profile.passage_prefix) == (query, passage)


def test_default_profile_keeps_existing_collections_without_prefixes() -> None:
    """Upgrading never hides documents indexed before prefixes existed."""
    profile = active_embedding_profile()
    model = "intfloat/multilingual-e5-base"

    assert profile == EmbeddingProfile(model, "", "")
    assert (
        profile.collection_name
        == f"parsrag_{hashlib.sha256(model.encode()).hexdigest()[:12]}"
    )


@pytest.mark.usefixtures("e5_prefixes")
def test_opting_in_uses_the_e5_prefixes() -> None:
    profile = active_embedding_profile()

    assert profile == EmbeddingProfile(
        "intfloat/multilingual-e5-base", "query: ", "passage: "
    )


def test_overrides_and_explicit_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMBED_QUERY_PREFIX", "search_query: ")
    monkeypatch.setenv("EMBED_PASSAGE_PREFIX", "none")

    profile = active_embedding_profile()

    assert profile.query_prefix == "search_query: "
    assert profile.passage_prefix == ""


@pytest.mark.usefixtures("e5_prefixes")
def test_empty_override_keeps_the_model_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EMBED_QUERY_PREFIX", "")
    monkeypatch.setenv("EMBED_PASSAGE_PREFIX", "  ")

    profile = active_embedding_profile()

    assert (profile.query_prefix, profile.passage_prefix) == ("query: ", "passage: ")


def test_collection_versions_include_prefixes() -> None:
    model = "intfloat/multilingual-e5-base"
    legacy = f"parsrag_{hashlib.sha256(model.encode()).hexdigest()[:12]}"

    prefixed = EmbeddingProfile(model, "query: ", "passage: ").collection_name
    plain = EmbeddingProfile(model, "", "").collection_name

    assert plain == legacy
    assert prefixed != legacy
    assert prefixed.startswith("parsrag_") and len(prefixed) == len(legacy)


@patch("backend.infrastructure.database.qdrant_repo.QdrantClient")
@patch("backend.infrastructure.database.qdrant_repo.Settings")
def test_repository_uses_the_profile_collection(
    mock_settings: MagicMock,
    mock_client_cls: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.infrastructure.database.qdrant_repo import QdrantRepository

    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)

    repository = QdrantRepository(vector_size=768)

    assert repository.collection_name == active_embedding_profile().collection_name


@pytest.mark.usefixtures("e5_prefixes")
@patch("backend.infrastructure.llm.factory.HuggingFaceEmbedding")
@patch("backend.infrastructure.llm.factory.configure_model")
@patch("backend.infrastructure.llm.factory.Settings")
def test_factory_configures_embedding_instructions(
    mock_settings: MagicMock, mock_configure: MagicMock, mock_embedding: MagicMock
) -> None:
    from backend.infrastructure.llm.factory import setup_llm_and_embeddings

    setup_llm_and_embeddings()

    kwargs = mock_embedding.call_args.kwargs
    assert kwargs["query_instruction"] == "query: "
    assert kwargs["text_instruction"] == "passage: "
