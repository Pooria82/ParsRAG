"""The answer language follows the question, not the documents or the examples."""

import pytest

from backend.core.strategies.prompt_rules import answer_language_rule, question_language


@pytest.mark.parametrize(
    ("question", "language"),
    [
        ("Which defenses did the report validate with pytest?", "en"),
        ("حملهٔ alg: none چطور اعتبارسنجی امضای توکن را دور می‌زند؟", "fa"),
        ("مشکل N+1 در ORM چیست و در SQLAlchemy چطور با Eager Loading حلش کنیم؟", "fa"),
        ("What does @{نیازمندی‌های تست.docx} say about static fields?", "en"),
        ("What does the word نیازمندی mean here?", "en"),
        ("خلاصهٔ `session.query(User).options(joinedload(User.posts))` چیست؟", "fa"),
        ("", "fa"),
        ("۱۲۳؟", "fa"),
    ],
)
def test_question_language(question: str, language: str) -> None:
    """English terms inside a Persian question do not make it English."""
    assert question_language(question) == language


def test_answer_language_rule_names_the_language() -> None:
    """The rule placed after the question names the language explicitly."""
    assert "in English" in answer_language_rule("What is ORM?")
    assert "in Persian" in answer_language_rule("ORM چیست؟")


@pytest.mark.parametrize("mode", ["strict", "hybrid", "llm_only"])
def test_every_prompt_ends_with_the_answer_language(mode: str) -> None:
    """Each mode states the answer language right before the answer starts."""
    from backend.core.strategies import hybrid_rag, llm_only, strict_rag

    template = {
        "strict": strict_rag.STRICT_RAG_PROMPT_TEMPLATE,
        "hybrid": hybrid_rag.HYBRID_RAG_PROMPT_TEMPLATE,
        "llm_only": llm_only.LLM_ONLY_PROMPT_TEMPLATE,
    }[mode]
    assert template.rstrip().endswith("{answer_language}\nAnswer:")
