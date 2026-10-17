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
# Clauses are joined by "و" / "and", optionally after a comma.
_CONNECTOR = re.compile(r"\s*[،,]?\s+(?:و|and)\s+", re.IGNORECASE)
_MIN_PART_WORDS = 3
_MAX_PARTS = 4


def _asks(text: str) -> bool:
    return bool(_QUESTION_WORD.search(text))


# Two questions in one message: "...چه بود؟ برای ... چه رویکردی؟"
_SENTENCE_END = re.compile(r"(?<=[؟?])\s+")


def question_parts(question: str) -> list[str]:
    """The separate questions inside ``question``; one item when it asks one thing."""
    text = question.strip()
    parts = [
        part
        for sentence in _SENTENCE_END.split(text)
        if sentence.strip()
        for part in _clause_parts(sentence.strip())
    ]
    return parts[:_MAX_PARTS] if len(parts) > 1 else [text]


def _clause_parts(sentence: str) -> list[str]:
    """Split one sentence at "و" / "and" where both sides ask something.

    A clause without its own question word stays with the clause before it,
    so "chapters one and two" or "unit and system tests" are not split.
    """
    pieces = _CONNECTOR.split(sentence)
    parts: list[str] = []
    current = pieces[0]
    for piece in pieces[1:]:
        if (
            _asks(current)
            and _asks(piece)
            and len(current.split()) >= _MIN_PART_WORDS
            and len(piece.split()) >= _MIN_PART_WORDS
        ):
            parts.append(current.strip(" ،,"))
            current = piece
        else:
            joiner = " and " if re.search(r"[A-Za-z]$", current) else " و "
            current = f"{current}{joiner}{piece}"
    parts.append(current.strip(" ،,"))
    return parts
