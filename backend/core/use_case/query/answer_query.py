"""Use case: answer a question in the requested trust and grounding mode."""

import logging
from collections.abc import Callable
from typing import TypedDict

from llama_index.core.llms import ChatMessage as LlamaChatMessage

from backend.core.domain.enums import QueryMode
from backend.core.domain.exceptions import InvalidInputError
from backend.core.dto.input.query import QueryRequest
from backend.core.dto.output.query import QueryResponse
from backend.core.port.document_repository import DocumentRepository
from backend.core.port.progress_tracker import ProgressCallback, ProgressTracker
from backend.core.port.query_strategy import QueryStrategy
from backend.core.port.question_condenser import QuestionCondenser
from backend.core.runtime.capacity import WorkLimiter
from backend.core.runtime.correlation import current_correlation_id
from backend.core.strategies.multi_doc_utils import parse_tagged_segments

logger = logging.getLogger("parsrag.operations")


class _ExecuteOptions(TypedDict, total=False):
    """Optional strategy arguments that are only sent when present."""

    progress: ProgressCallback
    document_segments: list[tuple[str, str]]


class AnswerQuery:
    """Condense, route, and execute one question through a query strategy.

    Pipeline: reserve a query slot, rewrite the follow-up into a standalone
    question, resolve explicit ``@{file}`` mentions against the session, then
    delegate retrieval and generation to the strategy selected for the mode.
    Coarse stages are published for the opaque request ID when one is given.
    """

    def __init__(
        self,
        repository: DocumentRepository,
        condenser_factory: Callable[[], QuestionCondenser],
        strategy_resolver: Callable[[QueryMode], QueryStrategy],
        progress: ProgressTracker,
        limiter: WorkLimiter,
    ) -> None:
        """Bind the ports; model-bound collaborators are built per request."""
        self._repository = repository
        self._condenser_factory = condenser_factory
        self._strategy_resolver = strategy_resolver
        self._progress = progress
        self._limiter = limiter

    def execute(self, request: QueryRequest) -> QueryResponse:
        """Answer the request and record its final progress stage.

        Raises:
            InvalidInputError: A document mention is invalid for the session.
            CapacityExceededError: Every query slot is busy.
        """
        request_id = str(request.request_id) if request.request_id else None
        try:
            with self._limiter.slot():
                response = self._answer(request, request_id)
        except Exception:
            if request_id:
                self._progress.set_stage(request_id, "failed")
            raise
        if request_id:
            self._progress.set_stage(request_id, "complete")
        return response

    def _answer(self, request: QueryRequest, request_id: str | None) -> QueryResponse:
        """Run the condense-route-execute pipeline inside a reserved slot."""
        logger.info(
            "query_started correlation_id=%s mode=%s",
            current_correlation_id(),
            request.mode,
        )
        if request_id:
            self._progress.set_stage(request_id, "understanding")
        chat_history = [
            LlamaChatMessage(role=message.role, content=message.content)
            for message in request.chat_history
        ]
        condensed_query = self._condenser_factory().condense(
            request.prompt, chat_history
        )
        strategy = self._strategy_resolver(request.mode)
        options = self._execute_options(request, request_id)
        response = strategy.execute(
            query=condensed_query,
            chat_history=chat_history,
            session_id=request.session_id,
            top_k=request.top_k,
            file_filter=request.file_filter,
            **options,
        )
        logger.info(
            "query_complete correlation_id=%s source_count=%d",
            current_correlation_id(),
            len(response.source_nodes),
        )
        return response

    def _execute_options(
        self, request: QueryRequest, request_id: str | None
    ) -> _ExecuteOptions:
        """Collect the progress callback and explicit document segments."""
        options: _ExecuteOptions = {}
        if request_id:
            options["progress"] = lambda stage: self._progress.set_stage(
                request_id, stage
            )
        segments = self._document_segments(request)
        if segments:
            options["document_segments"] = segments
        return options

    def _document_segments(self, request: QueryRequest) -> list[tuple[str, str]]:
        """Resolve ``@{file}`` mentions to session files within the active filter."""
        if request.mode is QueryMode.LLM_ONLY or "@{" not in request.prompt:
            return []
        try:
            available_files = self._repository.get_session_files(
                request.session_id or ""
            )
            if request.file_filter is not None:
                available_files = [
                    filename
                    for filename in available_files
                    if filename in request.file_filter
                ]
            return parse_tagged_segments(request.prompt, available_files)
        except ValueError as exc:
            raise InvalidInputError(str(exc)) from exc
