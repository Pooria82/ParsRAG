"""ParsRAG Chainlit Frontend Application Entrypoint.

Thin declarative orchestrator wiring Chainlit lifecycle hooks to dedicated handlers:
- SettingsBuilder: comprehensive chat configuration widgets loaded from .env.
- SessionManager: user session state tracking (language, mode, thresholds, memory).
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
from frontend.ui.i18n import (
    format_language_switched,
    format_settings_updated,
    get_welcome_markdown,
    normalize_language,
)
from frontend.ui.settings_builder import SettingsBuilder

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
    initial_lang = config.default_language
    session_manager.initialize_session(
        default_language=initial_lang,
        default_mode=config.default_mode,
        default_strict_rag_threshold=config.strict_rag_threshold,
        default_dynamic_top_k=config.dynamic_retrieval_depth,
        default_manual_top_k=config.default_top_k,
        default_top_k=None if config.dynamic_retrieval_depth else config.default_top_k,
        default_max_chat_history_turns=config.max_chat_history_turns,
        default_backend_url=config.backend_url,
    )
    await settings_builder.build(lang=initial_lang).send()
    await cl.Message(content=get_welcome_markdown(initial_lang)).send()


@cl.on_settings_update
async def on_settings_update(settings: dict[str, Any]) -> None:
    """Synchronizes UI settings widget modifications with session state."""
    # 1. Language
    raw_lang = str(settings.get("language", session_manager.get_language()))
    new_lang = normalize_language(raw_lang)
    old_lang = session_manager.get_language()
    session_manager.set_language(new_lang)

    # 2. RAG Mode
    raw_mode = str(settings.get("mode", "Hybrid RAG"))
    mode = parse_mode(raw_mode)
    session_manager.set_mode(mode)

    # 3. Strict Threshold
    raw_threshold = settings.get("strict_rag_threshold", config.strict_rag_threshold)
    threshold = float(raw_threshold)
    session_manager.set_strict_rag_threshold(threshold)

    # 4. Dynamic Depth Switch
    dynamic_depth = bool(settings.get("dynamic_depth", config.dynamic_retrieval_depth))
    session_manager.set_dynamic_top_k(dynamic_depth)

    # 5. Manual Depth
    raw_manual_k = settings.get("manual_top_k", config.default_top_k)
    manual_top_k = int(raw_manual_k)
    session_manager.set_manual_top_k(manual_top_k)
    effective_top_k = None if dynamic_depth else manual_top_k
    session_manager.set_top_k(effective_top_k)

    # 6. History Window
    raw_turns = settings.get("max_history_turns", config.max_chat_history_turns)
    max_turns = int(raw_turns)
    session_manager.set_max_chat_history_turns(max_turns)

    # 7. Backend URL
    backend_url = str(settings.get("backend_url", config.backend_url)).strip()
    session_manager.set_backend_url(backend_url)
    api_client.base_url = backend_url

    # If language changed, notify user and re-send updated settings drawer
    if new_lang != old_lang:
        await cl.Message(content=format_language_switched(new_lang)).send()
        await settings_builder.build(lang=new_lang).send()

    status_text = format_settings_updated(
        lang=new_lang,
        raw_mode=raw_mode,
        normalized_mode=mode,
        dynamic_depth=dynamic_depth,
        top_k=effective_top_k,
        threshold=threshold,
    )
    await cl.Message(content=status_text).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Delegates message processing to upload, control commands, and query handlers."""
    prompt_text = (message.content or "").strip()

    # Fast control commands dispatched from bottom bar mode and language pills
    if prompt_text.startswith("/mode "):
        target_mode = parse_mode(prompt_text.replace("/mode ", "").strip())
        session_manager.set_mode(target_mode)
        lang = session_manager.get_language()
        confirm_text = (
            f"🎯 Mode switched to `{target_mode}`."
            if lang == "en"
            else f"🎯 حالت کاری به `{target_mode}` تغییر یافت."
        )
        await cl.Message(content=confirm_text).send()
        return

    if prompt_text.startswith("/lang "):
        target_lang = normalize_language(prompt_text.replace("/lang ", "").strip())
        session_manager.set_language(target_lang)
        await cl.Message(content=format_language_switched(target_lang)).send()
        await settings_builder.build(lang=target_lang).send()
        return

    # 1. Handle file uploads if attached
    if message.elements:
        await upload_handler.handle_uploads(message.elements)

    # 2. Handle text prompt if provided
    if prompt_text:
        await query_handler.handle_query(prompt_text)
