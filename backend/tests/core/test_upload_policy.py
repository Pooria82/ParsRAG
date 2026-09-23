"""Tests for environment-driven ingestion limits."""

import pytest

from backend.core.upload_policy import UploadPolicy


def test_upload_policy_defaults_support_ten_large_documents(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default capacity matches the product contract without code duplication."""
    for name in (
        "PARSRAG_MAX_FILES_PER_SESSION",
        "PARSRAG_MAX_FILE_BYTES",
        "PARSRAG_MAX_BATCH_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)

    policy = UploadPolicy.from_environment()

    assert policy.max_files_per_session == 10
    assert policy.max_file_bytes == 100 * 1024 * 1024
    assert policy.max_batch_bytes == 500 * 1024 * 1024
    assert {".pdf", ".docx", ".pptx", ".txt", ".md", ".json", ".png"} <= set(
        policy.supported_extensions
    )


def test_upload_policy_clamps_unsafe_environment_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed .env cannot disable capacity safety boundaries."""
    monkeypatch.setenv("PARSRAG_MAX_FILES_PER_SESSION", "999")
    monkeypatch.setenv("PARSRAG_MAX_FILE_BYTES", "invalid")
    monkeypatch.setenv("PARSRAG_MAX_BATCH_BYTES", "1")

    policy = UploadPolicy.from_environment()

    assert policy.max_files_per_session == 50
    assert policy.max_file_bytes == 100 * 1024 * 1024
    assert policy.max_batch_bytes >= policy.max_file_bytes
