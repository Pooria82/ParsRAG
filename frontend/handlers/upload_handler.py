"""Handler for document uploads and indexing."""

import asyncio
import os
from pathlib import Path
from typing import Any

import chainlit as cl
import httpx

from frontend.client import ParsRAGClient
from frontend.config import FrontendConfig
from frontend.models import UploadItem
from frontend.services.session_manager import SessionManager
from frontend.ui.strings import (
    format_file_limit_exceeded,
    format_ingest_error,
    format_ingest_progress,
    format_ingest_success,
)


class UploadHandler:
    """Handles extraction, validation, and ingestion of documents attached to chat messages."""

    def __init__(
        self,
        client: ParsRAGClient,
        session_manager: SessionManager,
        config: FrontendConfig | None = None,
    ) -> None:
        """Initializes the upload handler.

        Args:
            client: ParsRAG API client.
            session_manager: Active session manager.
            config: Optional configuration instance.
        """
        self.client = client
        self.session_manager = session_manager
        self.config = config or FrontendConfig()

    async def extract_upload_items(self, elements: list[Any]) -> list[UploadItem]:
        """Extracts and reads binary contents of attached files asynchronously.

        Args:
            elements: List of elements from Chainlit message.

        Returns:
            list[UploadItem]: List of extracted UploadItem models.
        """
        items: list[UploadItem] = []
        for elem in elements:
            file_path = getattr(elem, "path", None)
            file_name = getattr(elem, "name", "document")
            file_bytes: bytes | None = None

            if file_path and os.path.exists(file_path):
                file_bytes = await asyncio.to_thread(Path(file_path).read_bytes)
            elif getattr(elem, "content", None):
                raw = elem.content
                if isinstance(raw, bytes):
                    file_bytes = raw

            if file_bytes is not None:
                items.append(UploadItem(filename=file_name, content=file_bytes))
        return items

    def validate_items(self, items: list[UploadItem], existing_count: int) -> None:
        """Validates file count, formats, and sizes against operational rules.

        Args:
            items: Upload items to validate.
            existing_count: Number of files already active in the session.

        Raises:
            ValueError: If file count, extension, or size violates constraints.
        """
        total = existing_count + len(items)
        if total > self.config.max_files_per_batch:
            raise ValueError(
                format_file_limit_exceeded(
                    current_count=existing_count,
                    new_count=len(items),
                    max_limit=self.config.max_files_per_batch,
                )
            )

        for item in items:
            ext = os.path.splitext(item.filename)[1].lower()
            if ext not in self.config.supported_extensions:
                allowed_str = ", ".join(sorted(self.config.supported_extensions))
                raise ValueError(
                    f"فرمت فایل '{item.filename}' مجاز نیست. فرمت‌های مجاز: {allowed_str}"
                )
            if item.size_bytes > self.config.max_file_size_bytes:
                raise ValueError(
                    f"حجم فایل '{item.filename}' از سقف مجاز ۵۰ مگابایت بیشتر است."
                )

    async def handle_uploads(self, elements: list[Any]) -> bool:
        """Coordinates file extraction, validation, and Qdrant ingestion.

        Args:
            elements: List of message elements attached by user.

        Returns:
            bool: True if files were attached and handled, False otherwise.
        """
        if not elements:
            return False

        items = await self.extract_upload_items(elements)
        if not items:
            return False

        existing_files = self.session_manager.get_uploaded_files()

        try:
            self.validate_items(items, existing_count=len(existing_files))
        except ValueError as val_err:
            await cl.Message(content=str(val_err)).send()
            return True

        ingest_msg = cl.Message(content=format_ingest_progress(len(items)))
        await ingest_msg.send()

        session_id = self.session_manager.get_session_id()
        payload_tuples = [(item.filename, item.content) for item in items]

        try:
            res = await self.client.ingest_files(payload_tuples, session_id=session_id)
            updated_files = self.session_manager.add_uploaded_files(
                [item.filename for item in items]
            )
            ingest_msg.content = format_ingest_success(
                backend_message=res.get("message", ""),
                active_files=updated_files,
            )
            await ingest_msg.update()
        except (ValueError, RuntimeError, httpx.RequestError) as exc:
            ingest_msg.content = format_ingest_error(str(exc))
            await ingest_msg.update()

        return True
