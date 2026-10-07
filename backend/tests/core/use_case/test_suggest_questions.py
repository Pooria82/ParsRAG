"""Document-specific question suggestions."""

from typing import Literal

import pytest

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.exceptions import InvalidInputError
from backend.core.dto.input.model import QuestionSuggestionRequest
from backend.core.runtime.capacity import WorkLimiter
from backend.core.use_case.model.suggest_questions import (
    SuggestQuestions,
    is_substantive,
)
from backend.infrastructure.llm.factory import _clean_questions
from backend.tests.core.use_case.fakes import InMemoryRepository


class RecordingGateway:
    """Capture the excerpts sent to the model."""

    def __init__(self) -> None:
        """Start without calls."""
        self.excerpts: list[str] = []

    def suggest_questions(
        self, excerpts: list[str], language: Literal["fa", "en"]
    ) -> list[str]:
        """Return four questions so the use case has to trim them."""
        self.excerpts = excerpts
        return ["الف؟", "ب؟", "ج؟", "د؟"]


def _use_case(
    repository: InMemoryRepository, gateway: RecordingGateway
) -> SuggestQuestions:
    return SuggestQuestions(repository, gateway, WorkLimiter(1, "query"))  # type: ignore[arg-type]


BUDGET = "بودجهٔ پروژه دویست میلیون تومان تعیین شد و صرف خرید سرور شد. " * 3
SCHEDULE = "زمان‌بندی اجرای پروژه شش ماه است و در سه مرحله انجام می‌شود. " * 3


def test_navigation_text_is_not_substantive() -> None:
    assert is_substantive(BUDGET)
    assert not is_substantive("فهرست مطالب " + BUDGET)
    assert not is_substantive("گزارش هفته اول ........ 4 " * 6)
    assert not is_substantive(
        "فصل ۱ ۲ ۳ ۴ ۵ ۶ ۷ ۸ ۹ ۱۰ ۱۱ ۱۲ ۱۳ ۱۴ ۱۵ ۱۶ ۱۷ ۱۸ ۱۹ ۲۰ " * 4
    )
    assert not is_substantive("کوتاه")


def test_questions_come_from_each_document_and_are_bounded() -> None:
    repository = InMemoryRepository()
    repository.save_nodes(
        [
            ExtractedNode(text=BUDGET, metadata={"filename": "a.pdf"}),
            ExtractedNode(text=SCHEDULE, metadata={"filename": "b.docx"}),
        ],
        session_id="s1",
    )
    gateway = RecordingGateway()

    result = _use_case(repository, gateway).execute("s1", QuestionSuggestionRequest())

    assert result.questions == ["الف؟", "ب؟", "ج؟"]
    assert any(excerpt.startswith("[a.pdf]") for excerpt in gateway.excerpts)
    assert any(excerpt.startswith("[b.docx]") for excerpt in gateway.excerpts)


def test_sessions_without_documents_need_no_model_call() -> None:
    gateway = RecordingGateway()
    result = _use_case(InMemoryRepository(), gateway).execute(
        "empty", QuestionSuggestionRequest(language="en")
    )
    assert result.questions == []
    assert gateway.excerpts == []


def test_selected_files_and_session_ids_are_respected() -> None:
    repository = InMemoryRepository()
    repository.save_nodes(
        [ExtractedNode(text="x", metadata={"filename": "a.pdf"})], session_id="s1"
    )
    gateway = RecordingGateway()
    result = _use_case(repository, gateway).execute(
        "s1", QuestionSuggestionRequest(files=["other.pdf"])
    )
    assert result.questions == []
    with pytest.raises(InvalidInputError):
        _use_case(repository, gateway).execute("../bad", QuestionSuggestionRequest())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            '```json\n["بودجه چقدر بود؟", "مدت اجرا؟؟", "چه ابزاری؟"]\n```',
            ["بودجه چقدر بود؟", "مدت اجرا؟؟", "چه ابزاری؟"],
        ),
        (
            "1. What was the budget?\n2) Who led it?\n- Why Odoo?",
            ["What was the budget?", "Who led it?", "Why Odoo?"],
        ),
        ('["same question?", "same question?", "ok"]', ["same question?"]),
    ],
)
def test_model_output_is_parsed_and_sanitized(raw: str, expected: list[str]) -> None:
    assert _clean_questions(raw) == expected
