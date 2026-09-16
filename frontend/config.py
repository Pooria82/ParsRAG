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
    default_language: str = os.getenv("DEFAULT_LANGUAGE", "fa")
    default_mode: str = os.getenv("DEFAULT_RAG_MODE", "hybrid")
    strict_rag_threshold: float = float(os.getenv("STRICT_RAG_THRESHOLD", "0.80"))
    dynamic_retrieval_depth: bool = (
        os.getenv("DYNAMIC_RETRIEVAL_DEPTH", "true").strip().lower() == "true"
    )
    max_files_per_batch: int = 5
    max_file_size_bytes: int = 50 * 1024 * 1024  # 50 MB
    supported_extensions: tuple[str, ...] = (".docx", ".pptx", ".pdf")
    default_top_k: int = int(os.getenv("RAG_TOP_K", "15"))
    min_top_k: int = 5
    max_top_k: int = 30
    step_top_k: int = 1
    stream_chunk_delay_sec: float = 0.008
    max_chat_history_turns: int = int(os.getenv("MAX_CHAT_HISTORY_TURNS", "10"))
    http_timeout_sec: float = 120.0
