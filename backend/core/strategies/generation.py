"""Shared generation step for strategies that prepare a prompt first.

Strategies implement ``prepare`` (retrieval, evidence gates, prompt). This
base turns a prepared prompt into a complete answer or a token stream, so the
blocking ``/query`` and the streaming ``/query/stream`` behave identically.
"""

from collections.abc import Iterator
from typing import Any

from llama_index.core.llms import ChatMessage

from backend.core.dto.output.query import PreparedAnswer, QueryResponse
from backend.core.port.progress_tracker import ProgressCallback
from backend.core.service.citations import extract_citations


def build_response(
    prepared: PreparedAnswer, answer: str | None = None
) -> QueryResponse:
    """Combine a prepared answer with generated text into the API response."""
    if prepared.prompt is None:
        return QueryResponse(
            answer=prepared.immediate, source_nodes=[], outcome=prepared.outcome
        )
    text = (answer or "").strip()
    return QueryResponse(
        answer=text,
        source_nodes=prepared.sources,
        cited=extract_citations(text, len(prepared.sources)),
    )


class GeneratingStrategy:
    """Generate from ``prepare``'s prompt with the strategy's language model."""

    llm: Any

    def prepare(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
        file_filter: list[str] | None = None,
        progress: ProgressCallback | None = None,
        document_segments: list[tuple[str, str]] | None = None,
    ) -> PreparedAnswer:
        """Retrieve evidence and build the prompt (implemented per mode)."""
        raise NotImplementedError

    def execute(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
        file_filter: list[str] | None = None,
        progress: ProgressCallback | None = None,
        document_segments: list[tuple[str, str]] | None = None,
    ) -> QueryResponse:
        """Prepare, then generate the whole answer in one model call."""
        prepared = self.prepare(
            query,
            chat_history,
            session_id=session_id,
            top_k=top_k,
            file_filter=file_filter,
            progress=progress,
            document_segments=document_segments,
        )
        if prepared.prompt is None:
            return build_response(prepared)
        if progress:
            progress("generating")
        return build_response(prepared, str(self.llm.complete(prepared.prompt)))

    def stream(self, prepared: PreparedAnswer) -> Iterator[str]:
        """Yield answer text as the model produces it."""
        if prepared.prompt is None:
            return
        for chunk in self.llm.stream_complete(prepared.prompt):
            delta = getattr(chunk, "delta", None)
            if delta:
                yield str(delta)
