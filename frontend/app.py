"""ParsRAG Chainlit Frontend Application Entrypoint.

Thin declarative orchestrator wiring Chainlit lifecycle hooks to dedicated handlers:
- SettingsBuilder: chat configuration widgets.
- SessionManager: user session state tracking.
- UploadHandler: document extraction, validation, and ingestion.
- QueryHandler: RAG query execution, token streaming, and citations.
"""

import sys
from pathlib import Path
from typing import Any

# Ensure repository root is on sys.path for chainlit runner
WORKSPACE_ROOT = str(Path(__file__).resolve().parent.parent)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

import chainlit as cl

from frontend.client import ParsRAGClient, parse_mode
from frontend.config import FrontendConfig
from frontend.handlers.query_handler import QueryHandler
from frontend.handlers.upload_handler import UploadHandler
from frontend.services.session_manager import SessionManager
from frontend.ui.settings_builder import SettingsBuilder
from frontend.ui.strings import WELCOME_MARKDOWN, format_settings_updated

# Core Application Dependencies
config = FrontendConfig()
api_client = ParsRAGClient(config=config)
session_manager = SessionManager()
settings_builder = SettingsBuilder(config=config)
upload_handler = UploadHandler(
    client=api_client, session_manager=session_manager, config=config
)
query_handler = QueryHandler(
    client=api_client, session_manager=session_manager, config=config
)


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initializes session state, interactive settings drawer, and welcome message."""
    session_manager.initialize_session(
        default_mode="hybrid",
        default_top_k=None,
    )
    await settings_builder.build().send()
    await cl.Message(content=WELCOME_MARKDOWN).send()


@cl.on_settings_update
async def on_settings_update(settings: dict[str, Any]) -> None:
    """Synchronizes UI settings widget modifications with session state."""
    raw_mode = str(settings.get("mode", "Hybrid RAG"))
    mode = parse_mode(raw_mode)
    session_manager.set_mode(mode)

    raw_top_k = settings.get("top_k")
    top_k = int(raw_top_k) if raw_top_k is not None else None
    session_manager.set_top_k(top_k)

    status_text = format_settings_updated(raw_mode, mode, top_k)
    await cl.Message(content=status_text).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Delegates message processing to upload and query handlers."""
    # 1. Handle file uploads if attached
    if message.elements:
        await upload_handler.handle_uploads(message.elements)

    # 2. Handle text prompt if provided
    prompt_text = (message.content or "").strip()
    if prompt_text:
        await query_handler.handle_query(prompt_text)
