"""Find which numbered context excerpts an answer cites."""

import re

_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
# [3], [1, 4], [۲]، and [1][2] (the latter matches twice).
_CITATION = re.compile(r"\[\s*([0-9۰-۹٠-٩]{1,3}(?:\s*[,،]\s*[0-9۰-۹٠-٩]{1,3})*)\s*\]")


def extract_citations(answer: str, source_count: int) -> list[int]:
    """Return cited 1-based source numbers in first-use order, ignoring others."""
    cited: list[int] = []
    for match in _CITATION.finditer(answer):
        for value in re.split(r"\s*[,،]\s*", match.group(1).translate(_DIGITS)):
            number = int(value)
            if 1 <= number <= source_count and number not in cited:
                cited.append(number)
    return cited
