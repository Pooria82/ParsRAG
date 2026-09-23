"""Single source of truth for safe document-ingestion capabilities."""

from __future__ import annotations

import os
from dataclasses import dataclass

OFFICE_EXTENSIONS = (".docx", ".pptx")
PDF_EXTENSIONS = (".pdf",)
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
TEXT_EXTENSIONS = (
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".csv",
    ".tsv",
    ".html",
    ".htm",
    ".xml",
    ".yaml",
    ".yml",
    ".log",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".sql",
    ".toml",
    ".ini",
    ".cfg",
)
SUPPORTED_EXTENSIONS = (
    *PDF_EXTENSIONS,
    *OFFICE_EXTENSIONS,
    *IMAGE_EXTENSIONS,
    *TEXT_EXTENSIONS,
)


def _bounded_environment_int(
    name: str, default: int, minimum: int, maximum: int
) -> int:
    """Read an integer environment variable inside a safe inclusive range."""
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


@dataclass(frozen=True)
class UploadPolicy:
    """Validated upload limits shared by validation and capability discovery."""

    max_files_per_session: int
    max_file_bytes: int
    max_batch_bytes: int
    supported_extensions: tuple[str, ...] = SUPPORTED_EXTENSIONS

    @classmethod
    def from_environment(cls) -> UploadPolicy:
        """Build the upload policy from bounded runtime settings."""
        max_files = _bounded_environment_int("PARSRAG_MAX_FILES_PER_SESSION", 10, 1, 50)
        max_file_bytes = _bounded_environment_int(
            "PARSRAG_MAX_FILE_BYTES",
            100 * 1024 * 1024,
            1024 * 1024,
            1024 * 1024 * 1024,
        )
        max_batch_bytes = _bounded_environment_int(
            "PARSRAG_MAX_BATCH_BYTES",
            500 * 1024 * 1024,
            max_file_bytes,
            2 * 1024 * 1024 * 1024,
        )
        return cls(
            max_files_per_session=max_files,
            max_file_bytes=max_file_bytes,
            max_batch_bytes=max(max_file_bytes, max_batch_bytes),
        )
