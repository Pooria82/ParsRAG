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


def test_answer_language_rule_names_the_language_and_starts_the_answer() -> None:
    """The rule names the language, asks to translate, and starts the answer in it."""
    persian = answer_language_rule("fa")
    english = answer_language_rule("en")
    assert (
        "in Persian" in persian and "even when the documents are in English" in persian
    )
    assert persian.endswith("پاسخ (به فارسی):")
    assert "in English" in english and "documents or examples are in Persian" in english
    assert english.endswith("Answer (in English):")


def test_a_question_without_words_takes_the_interface_language() -> None:
    assert question_language("$x^2 + 1$ ?", "en") == "en"
    assert question_language("@{report.pdf} ؟", "fa") == "fa"
    # A question with words keeps its own language whatever the interface.
    assert question_language("What is ORM?", "fa") == "en"
    assert question_language("ORM چیست؟", "en") == "fa"


@pytest.mark.parametrize("mode", ["strict", "hybrid", "llm_only"])
def test_every_prompt_ends_with_the_answer_language(mode: str) -> None:
    """Each mode states the answer language right before the answer starts."""
    from backend.core.strategies import hybrid_rag, llm_only, strict_rag

    template = {
        "strict": strict_rag.STRICT_RAG_PROMPT_TEMPLATE,
        "hybrid": hybrid_rag.HYBRID_RAG_PROMPT_TEMPLATE,
        "llm_only": llm_only.LLM_ONLY_PROMPT_TEMPLATE,
    }[mode]
    assert template.rstrip().splitlines()[-1] == "{answer_language}"


@pytest.mark.parametrize(
    "question",
    ["@{" * 20000, "@{" + "\\|" * 20000, "`" * 20000],
    ids=["repeated-mentions", "escapes", "backticks"],
)
def test_question_language_is_fast_on_unclosed_markup(question: str) -> None:
    import time

    started = time.perf_counter()
    question_language(question)

    assert time.perf_counter() - started < 1.0


def test_escaped_braces_stay_inside_a_mention() -> None:
    assert question_language(r"What does @{report \{v2\} نهایی.docx} say?") == "en"
