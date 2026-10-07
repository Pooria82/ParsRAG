"""Inbound commands for document ingestion.

Uploads stay as readable streams so the use case can enforce byte limits while
reading instead of after a driving adapter has buffered the whole body.
"""

from dataclasses import dataclass
from typing import BinaryIO


@dataclass(frozen=True)
class IncomingFile:
    """One uploaded file exposed as a bounded-read stream."""

    filename: str | None
    stream: BinaryIO


@dataclass(frozen=True)
class IngestDocumentsCommand:
    """A batch of files to index into one isolated session."""

    session_id: str
    files: list[IncomingFile]
