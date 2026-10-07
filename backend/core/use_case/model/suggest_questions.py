"""Use case: propose questions the session's documents can answer."""

import re

from backend.core.domain.exceptions import InvalidInputError
from backend.core.domain.session import INVALID_SESSION_ID_MESSAGE, is_valid_session_id
from backend.core.dto.input.model import QuestionSuggestionRequest
from backend.core.dto.output.model import QuestionSuggestionResponse
from backend.core.port.document_repository import DocumentRepository
from backend.core.port.model_gateway import ModelGateway
from backend.core.runtime.capacity import WorkLimiter

# Probes for substantive passages: goals, methods, and findings, in both
# languages. Tables of contents match every probe, so they are filtered out.
_PROBES = (
    "هدف و موضوع اصلی main goal and topic",
    "روش انجام کار و ابزارها method and tools",
    "نتایج، یافته‌ها و نتیجه‌گیری results findings conclusion",
)
_PASSAGES_PER_PROBE = 4
_PASSAGES_PER_FILE = 3
_MAX_FILES = 4
_MAX_PASSAGE_CHARS = 700
_NAVIGATION = re.compile(
    r"فهرست\s*(?:مطالب|جداول|اشکال|تصاویر)|table of contents|\.{4,}|…{2,}",
    re.IGNORECASE,
)


def is_substantive(text: str) -> bool:
    """Reject tables of contents, page lists, and other navigation text."""
    if _NAVIGATION.search(text):
        return False
    letters = sum(char.isalpha() for char in text)
    digits = sum(char.isdigit() for char in text)
    return letters >= 80 and digits <= letters * 0.15


class SuggestQuestions:
    """Read a few representative passages and ask the model for questions."""

    def __init__(
        self,
        repository: DocumentRepository,
        gateway: ModelGateway,
        limiter: WorkLimiter,
    ) -> None:
        """Bind the repository, the model gateway, and the query limiter."""
        self._repository = repository
        self._gateway = gateway
        self._limiter = limiter

    def execute(
        self, session_id: str, request: QuestionSuggestionRequest
    ) -> QuestionSuggestionResponse:
        """Return up to three specific questions, or none without documents.

        Raises:
            InvalidInputError: The session ID is malformed.
            CapacityExceededError: Every model-work slot is busy.
        """
        if not is_valid_session_id(session_id):
            raise InvalidInputError(INVALID_SESSION_ID_MESSAGE, code="invalid_session")
        files = self._repository.get_session_files(session_id)
        if request.files is not None:
            files = [name for name in files if name in request.files]
        excerpts: list[str] = []
        for filename in files[:_MAX_FILES]:
            chosen: list[str] = []
            for probe in _PROBES:
                for node in self._repository.similarity_search(
                    probe,
                    top_k=_PASSAGES_PER_PROBE,
                    session_id=session_id,
                    file_filter=[filename],
                ):
                    if is_substantive(node.text) and node.text not in chosen:
                        chosen.append(node.text)
                        break
            excerpts.extend(
                f"[{filename}] {text[:_MAX_PASSAGE_CHARS]}"
                for text in chosen[:_PASSAGES_PER_FILE]
            )
        if not excerpts:
            return QuestionSuggestionResponse(questions=[])
        with self._limiter.slot():
            questions = self._gateway.suggest_questions(excerpts, request.language)
        return QuestionSuggestionResponse(questions=questions[:3])
