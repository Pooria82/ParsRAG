"""Split a question that asks several things into its parts.

"Which key opens Edit mode, and which fields did the example add?" asks two
things whose answers can sit far apart in a document. A single search finds
the passage for the first part and misses the second, so each part is also
searched on its own.

Only clauses that each carry their own question word are split, so "unit and
system tests" or "the cost and the schedule of phase two" stay one question.
"""

from __future__ import annotations

import re

_QUESTION_WORDS = (
    # Persian
    "چه",
    "چند",
    "چندم",
    "چندتا",
    "کدام",
    "کدامین",
    "چگونه",
    "چطور",
    "چرا",
    "کجا",
    "کی",
    "آیا",
    "چیست",
    "چیه",
    "چقدر",
    "کیست",
    "چه‌کسی",
    # English
    "what",
    "which",
    "how",
    "why",
    "where",
    "when",
    "who",
    "whom",
    "whose",
)
# A question word on its own, not inside a longer word ("چهار", "showcase").
_QUESTION_WORD = re.compile(
    r"(?<![\w‌])(?:"
    + "|".join(sorted(map(re.escape, _QUESTION_WORDS), key=len, reverse=True))
    + r")(?![\w‌])",
    re.IGNORECASE,
)
# Clauses are joined by "و" / "and" as separate words, optionally after a comma.
# Questions are split on words rather than with a regular expression, so the
# time stays linear whatever the user types.
_CONNECTORS = frozenset({"و", "and"})
_MIN_PART_WORDS = 3
_MAX_PARTS = 4


def _asks(text: str) -> bool:
    return bool(_QUESTION_WORD.search(text))


# Two questions in one message: "...چه بود؟ برای ... چه رویکردی؟"
_QUESTION_MARKS = frozenset("؟?")


def question_parts(question: str) -> list[str]:
    """The separate questions inside ``question``; one item when it asks one thing."""
    text = question.strip()
    parts = [part for sentence in _sentences(text) for part in _clause_parts(sentence)]
    return parts[:_MAX_PARTS] if len(parts) > 1 else [text]


def _sentences(text: str) -> list[str]:
    """Split after each question mark that ends a sentence (followed by a space)."""
    sentences: list[str] = []
    start = 0
    for index, char in enumerate(text):
        if (
            char in _QUESTION_MARKS
            and index + 1 < len(text)
            and text[index + 1].isspace()
        ):
            sentences.append(text[start : index + 1])
            start = index + 1
    sentences.append(text[start:])
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _clauses(sentence: str) -> tuple[list[str], list[str]]:
    """The clauses between connector words, and the connector before each one."""
    words = sentence.split()
    clauses: list[list[str]] = [[]]
    connectors: list[str] = []
    for index, word in enumerate(words):
        if word.casefold() in _CONNECTORS and clauses[-1] and index + 1 < len(words):
            connectors.append(word)
            clauses.append([])
        else:
            clauses[-1].append(word)
    return [" ".join(clause) for clause in clauses], connectors


def _clause_parts(sentence: str) -> list[str]:
    """Split one sentence at "و" / "and" where both sides ask something.

    A clause without its own question word stays with the clause before it,
    so "chapters one and two" or "unit and system tests" are not split.
    """
    pieces, connectors = _clauses(sentence)
    parts: list[str] = []
    current = pieces[0]
    for piece, connector in zip(pieces[1:], connectors, strict=True):
        if (
            _asks(current)
            and _asks(piece)
            and len(current.split()) >= _MIN_PART_WORDS
            and len(piece.split()) >= _MIN_PART_WORDS
        ):
            parts.append(current.strip(" ،,"))
            current = piece
        else:
            current = f"{current} {connector} {piece}"
    parts.append(current.strip(" ،,"))
    return parts
