"""Prompt rules shared by every answer strategy.

Keeping language, formatting, and citation rules in one place means the three
modes cannot drift apart, and every mode emits math the frontend can render.
LlamaIndex leaves unknown ``{...}`` placeholders untouched, so LaTeX braces
are written literally.
"""

import re

LANGUAGE_RULES = """\
LANGUAGE RULES:
1. Answer in the natural language of the user's question: Persian (فارسی) questions get a Persian answer, English questions an English answer. The language of the documents does not matter: translate what you use from them.
2. Code, commands, function names, and technical terms are usually English. Do not treat them as a sign that the question is in English; decide from the surrounding sentences.
3. Never answer in Chinese or any other unintended language."""

FORMATTING_RULES = """\
FORMATTING RULES:
1. Use Markdown for structure (short paragraphs, lists, tables when they help).
2. Write every mathematical expression in LaTeX inside math delimiters: $...$ inline and $$...$$ on its own line for display. Never leave LaTeX commands such as \\sin or \\frac outside delimiters, and always close every delimiter you open.
3. Keep Persian words outside math delimiters. Inside math use only symbols, numbers, Latin variables, and \\text{...} for short labels."""

CITATION_RULES = """\
CITATION RULES:
- Every context excerpt starts with a number in square brackets, such as [2]. Right after each sentence or paragraph that uses an excerpt, cite it with that number: [2], or [1][3] for several. Write the digits inside the brackets in ASCII (1, 2, 3) even in a Persian answer.
- Cite only numbers that appear in the context. Never invent a number, a file name, or a page; do not write file names or page numbers as citations.
- A page-boundary excerpt joins the end of one page to the start of the next. Read both parts together.
- An excerpt whose header includes `image: N` is text read from image N of that document. When you use it, say that the information appears in that image ("در تصویر N" / "in image N").
- If the user asks about a specific document, focus on that document and name it when relevant."""

_PERSIAN_WORD = re.compile(r"[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]+")
_LATIN_WORD = re.compile(r"[A-Za-z]+")
# Code spans, @{file} mentions, and links say nothing about the question's language.
# A mention stops at the next brace and a backslash only starts an escape, so
# unclosed or repeated "@{" cannot make matching slow.
_NEUTRAL = re.compile(r"`[^`]*`|@\{(?:\\.|[^{}\\])*\}|https?://\S+")


def question_language(question: str, fallback: str = "fa") -> str:
    """Return ``"fa"`` or ``"en"``: the language the answer should be written in.

    English technical terms are common inside Persian questions, so a question
    counts as Persian when Persian words make up more than a third of its words.
    A question without words in either script (a formula, a file mention) takes
    ``fallback``: the interface language when the browser sends it.
    """
    text = _NEUTRAL.sub(" ", question)
    persian = len(_PERSIAN_WORD.findall(text))
    latin = len(_LATIN_WORD.findall(text))
    if not persian:
        return "en" if latin else ("en" if fallback == "en" else "fa")
    return "fa" if persian * 2 > latin else "en"


def answer_language_rule(language: str) -> str:
    """The instruction that ends every prompt: the answer language, then its start.

    The general language rules and the bilingual examples in the prompt are not
    enough on their own: models answered English questions in Persian, and
    Persian questions about English documents in English. Naming the language
    last and starting the answer in it keeps small models in that language.
    """
    if language == "fa":
        return (
            "ANSWER LANGUAGE: The question is in Persian. Write the whole answer in "
            "Persian (فارسی), even when the documents are in English: translate what "
            "you use from them. Keep code, commands, and names as written.\n"
            "پاسخ (به فارسی):"
        )
    return (
        "ANSWER LANGUAGE: The question is in English. Write the whole answer in "
        "English, even when the documents or examples are in Persian: translate what "
        "you use from them. Keep code, commands, and names as written.\n"
        "Answer (in English):"
    )


CODE_VERIFICATION_RULES = """\
CODE AND CONCEPT CHECKS:
If the user asks whether a code snippet, function, command, library, or concept appears in the documents, compare it by meaning and structure, ignoring formatting differences (whitespace, parentheses, omitted declarations, reworded comments). If it is present, confirm it ("بله، این اطلاعات/کد در سند وجود دارد" or "Yes, this information/code is present in the document") and quote the relevant part with its citation number."""
