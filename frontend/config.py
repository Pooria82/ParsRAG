"""Configuration module for ParsRAG frontend."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FrontendConfig:
    """Operational settings for the ParsRAG Chainlit frontend.

    Attributes:
        backend_url: Root URL of the FastAPI backend service.
        max_files_per_batch: Maximum number of files permitted per session.
        max_file_size_bytes: Maximum allowed file size in bytes (50 MB).
        supported_extensions: Allowed file extensions for document ingestion.
        default_top_k: Default retrieval depth for Qdrant searches.
        min_top_k: Minimum retrieval depth slider boundary.
        max_top_k: Maximum retrieval depth slider boundary.
        step_top_k: Slider step increment.
        stream_chunk_delay_sec: Async sleep interval between progressive tokens.
        max_chat_history_turns: Maximum conversation turns preserved in memory.
        http_timeout_sec: HTTP request timeout in seconds.
    """

    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    max_files_per_batch: int = 5
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    supported_extensions: tuple[str, ...] = (".docx", ".pptx", ".pdf")
    default_top_k: int = 15
    min_top_k: int = 5
    max_top_k: int = 30
    step_top_k: int = 5
    stream_chunk_delay_sec: float = 0.008
    max_chat_history_turns: int = 10
    http_timeout_sec: float = 120.0
