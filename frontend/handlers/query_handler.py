"""Handler for executing RAG queries, progressive streaming, and citations."""

import asyncio
import re
from typing import Any

import chainlit as cl
import httpx

from frontend.client import ParsRAGClient
from frontend.config import FrontendConfig
from frontend.services.session_manager import SessionManager
from frontend.ui.citation_builder import CitationBuilder
from frontend.ui.strings import format_query_error


class QueryHandler:
    """Coordinates RAG queries, response token streaming, citations, and conversation history."""

    def __init__(
        self,
        client: ParsRAGClient,
        session_manager: SessionManager,
        citation_builder: CitationBuilder | None = None,
        config: FrontendConfig | None = None,
    ) -> None:
        """Initializes the query handler.

        Args:
            client: ParsRAG API client.
            session_manager: Active session manager.
            citation_builder: Optional citation UI builder.
            config: Optional configuration instance.
        """
        self.client = client
        self.session_manager = session_manager
        self.citation_builder = citation_builder or CitationBuilder()
        self.config = config or FrontendConfig()

    async def handle_query(self, prompt: str) -> None:
        """Executes query against the backend, streams response tokens, and attaches citations.

        Args:
            prompt: User question or command text.
        """
        clean_prompt = prompt.strip()
        if not clean_prompt:
            return

        response_msg = cl.Message(content="")
        await response_msg.send()

        session_id = self.session_manager.get_session_id()
        mode = self.session_manager.get_mode()
        lang = self.session_manager.get_language()
        dynamic = self.session_manager.get_dynamic_top_k()
        top_k = None if dynamic else self.session_manager.get_manual_top_k()
        chat_history = self.session_manager.get_chat_history()
        history_window = self.session_manager.get_max_chat_history_turns()

        try:
            query_res = await self.client.query(
                prompt=clean_prompt,
                chat_history=chat_history,
                mode=mode,
                session_id=session_id,
                top_k=top_k,
            )

            answer_text = str(query_res.get("answer", ""))
            source_nodes: list[dict[str, Any]] = query_res.get("source_nodes", [])

            # Progressive streaming with word/whitespace chunks
            tokens = re.findall(r"\S+|\s+", answer_text)
            for token in tokens:
                await response_msg.stream_token(token)
                await asyncio.sleep(self.config.stream_chunk_delay_sec)

            # Build and attach collapsible source citations in active language
            citation_elements = self.citation_builder.build_elements(
                source_nodes, lang=lang
            )
            if citation_elements:
                response_msg.elements = citation_elements
                await response_msg.update()

            # Record turn in conversational memory
            self.session_manager.append_chat_turn(
                prompt=clean_prompt,
                answer=answer_text,
                max_turns=history_window,
            )

        except (RuntimeError, ValueError, httpx.RequestError) as exc:
            error_md = format_query_error(str(exc), lang=lang)
            await response_msg.stream_token(error_md)
            await response_msg.update()
