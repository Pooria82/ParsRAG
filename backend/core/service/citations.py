"""Find which numbered context excerpts an answer cites."""

import re

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
# [3], [1, 4], [۲]، and [1][2] (the latter matches twice).
_CITATION = re.compile(r"\[\s*([0-9۰-۹٠-٩]{1,3}(?:\s*[,،]\s*[0-9۰-۹٠-٩]{1,3})*)\s*\]")
# Spans whose brackets are not citations: code, then display and inline math.
# Longer delimiters come first so "$$" is not read as two "$".
_SPANS = (
    ("```", "```"),
    ("`", "`"),
    ("$$", "$$"),
    ("\\[", "\\]"),
    ("\\(", "\\)"),
    ("$", "$"),
)


def without_code_and_math(answer: str) -> str:
    """Blank out code and math so ``[1, 3]`` in an interval is not a citation.

    A single pass with ``str.find`` keeps the time linear in the answer length;
    an unclosed delimiter leaves the rest of the text as it is.
    """
    parts: list[str] = []
    index = 0
    while index < len(answer):
        for opening, closing in _SPANS:
            if answer.startswith(opening, index):
                end = answer.find(closing, index + len(opening))
                if end != -1:
                    stop = end + len(closing)
                    parts.append(" " * (stop - index))
                    index = stop
                    break
        else:
            parts.append(answer[index])
            index += 1
    return "".join(parts)


def extract_citations(answer: str, source_count: int) -> list[int]:
    """Return cited 1-based source numbers in first-use order, ignoring others."""
    cited: list[int] = []
    for match in _CITATION.finditer(without_code_and_math(answer)):
        for value in re.split(r"\s*[,،]\s*", match.group(1).translate(_DIGITS)):
            number = int(value)
            if 1 <= number <= source_count and number not in cited:
                cited.append(number)
    return cited
