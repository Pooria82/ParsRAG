"""API client for connecting frontend to the ParsRAG FastAPI backend."""

import os
from typing import Any

import httpx

from frontend.config import FrontendConfig
from frontend.ui.citation_builder import CitationBuilder

_CONFIG = FrontendConfig()
DEFAULT_BACKEND_URL: str = _CONFIG.backend_url
SUPPORTED_EXTENSIONS: set[str] = set(_CONFIG.supported_extensions)
MAX_FILES_PER_BATCH: int = _CONFIG.max_files_per_batch
MAX_FILE_SIZE_BYTES: int = _CONFIG.max_file_size_bytes

MODE_MAP: dict[str, str] = {
    "Strict RAG": "strict",
    "Strict RAG (فقط اسناد)": "strict",
    "strict": "strict",
    "Hybrid RAG": "hybrid",
    "Hybrid RAG (ترکیبی)": "hybrid",
    "hybrid": "hybrid",
    "LLM Only": "llm-only",
    "LLM Only (فقط مدل)": "llm-only",
    "llm-only": "llm-only",
}


def parse_mode(mode_label: str) -> str:
    """Normalizes UI display labels or arbitrary strings into API QueryMode strings.

    Args:
        mode_label: The display label (e.g. 'Strict RAG' or 'Hybrid RAG (ترکیبی)').

    Returns:
        str: Normalized mode identifier ('strict', 'hybrid', or 'llm-only').
    """
    return MODE_MAP.get(mode_label.strip(), "hybrid")


def format_citation(node: dict[str, Any], index: int) -> tuple[str, str]:
    """Formats a retrieved source node into a title and markdown content.

    Backwards-compatible helper delegating to CitationBuilder.

    Args:
        node: Extracted node dictionary containing 'text', 'metadata', and optional 'score'.
        index: The 1-based index number of the citation.

    Returns:
        tuple[str, str]: (citation_name, citation_content) suitable for Chainlit Text elements.
    """
    item = CitationBuilder.parse_node(node, index)
    return item.title, item.body


class ParsRAGClient:
    """Async client interacting with the ParsRAG backend endpoints."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        config: FrontendConfig | None = None,
    ) -> None:
        """Initializes the ParsRAG API client.

        Args:
            base_url: Optional root URL override of the FastAPI backend.
            timeout: Optional HTTP request timeout in seconds override.
            config: Optional FrontendConfig instance.
        """
        cfg = config or _CONFIG
        self.base_url = (base_url or cfg.backend_url).rstrip("/")
        self.timeout = timeout if timeout is not None else cfg.http_timeout_sec
        self.config = cfg

    async def check_health(self) -> bool:
        """Checks if the FastAPI backend is operational and reachable.

        Returns:
            bool: True if backend responds with HTTP 200, False otherwise.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except httpx.RequestError:
            return False

    async def ingest_files(
        self,
        files: list[tuple[str, bytes]],
        session_id: str | None = None,
    ) -> dict[str, str]:
        """Uploads and ingests 1 to 5 documents into Qdrant for a session.

        Args:
            files: List of tuples containing (filename, file_bytes).
            session_id: Optional session identifier for isolated indexing.

        Returns:
            dict[str, str]: JSON response dictionary from the backend.

        Raises:
            ValueError: If file count, extension, or size violates constraints.
            RuntimeError: If the backend returns an error or fails to connect.
        """
        if not files:
            raise ValueError("هیچ فایلی برای بارگذاری ارائه نشده است.")

        if len(files) > self.config.max_files_per_batch:
            raise ValueError(
                f"حداکثر {self.config.max_files_per_batch} فایل می‌تواند در یک درخواست بارگذاری شود."
            )

        for fname, fbytes in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in self.config.supported_extensions:
                allowed_str = ", ".join(sorted(self.config.supported_extensions))
                raise ValueError(
                    f"فرمت فایل '{fname}' پشتیبانی نمی‌شود. فرمت‌های مجاز: {allowed_str}"
                )
            if len(fbytes) > self.config.max_file_size_bytes:
                raise ValueError(
                    f"حجم فایل '{fname}' از سقف مجاز ۵۰ مگابایت بیشتر است."
                )

        multipart_files = [
            ("files", (fname, fbytes, "application/octet-stream"))
            for fname, fbytes in files
        ]
        data_payload: dict[str, str] = {}
        if session_id:
            data_payload["session_id"] = session_id

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/ingest",
                    files=multipart_files,
                    data=data_payload,
                )
                if resp.status_code != 200:
                    detail = "خطای سرور"
                    try:
                        error_json = resp.json()
                        detail = str(error_json.get("detail", resp.text))
                    except (ValueError, KeyError):
                        detail = resp.text
                    raise RuntimeError(
                        f"خطا در پردازش اسناد ({resp.status_code}): {detail}"
                    )

                result: dict[str, str] = resp.json()
                return result
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"خطای ارتباط با سرور بک‌اند در آدرس {self.base_url}: {exc}"
            ) from exc

    async def query(
        self,
        prompt: str,
        chat_history: list[dict[str, str]] | None = None,
        mode: str = "hybrid",
        session_id: str | None = None,
        top_k: int | None = None,
        file_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        """Queries the ParsRAG system.

        Args:
            prompt: User question or instruction.
            chat_history: List of previous conversation turns.
            mode: Query mode ('strict', 'hybrid', or 'llm-only').
            session_id: Session identifier to retrieve scoped documents.
            top_k: Optional retrieval depth override.
            file_filter: Optional list of target filenames to restrict search.

        Returns:
            dict[str, Any]: Response dictionary with 'answer' and 'source_nodes'.

        Raises:
            RuntimeError: If query execution fails or backend returns an error.
        """
        payload: dict[str, Any] = {
            "prompt": prompt,
            "chat_history": chat_history or [],
            "mode": parse_mode(mode),
        }
        if session_id:
            payload["session_id"] = session_id
        if top_k is not None:
            payload["top_k"] = top_k
        if file_filter:
            payload["file_filter"] = file_filter

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/query",
                    json=payload,
                )
                if resp.status_code != 200:
                    detail = "خطای سرور"
                    try:
                        error_json = resp.json()
                        detail = str(error_json.get("detail", resp.text))
                    except (ValueError, KeyError):
                        detail = resp.text
                    raise RuntimeError(
                        f"خطا در پاسخ به پرسش ({resp.status_code}): {detail}"
                    )

                data: dict[str, Any] = resp.json()
                return data
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"عدم دسترسی به سرور بک‌اند در آدرس {self.base_url}: {exc}"
            ) from exc
