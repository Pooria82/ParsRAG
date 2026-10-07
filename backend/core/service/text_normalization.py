"""Canonical Persian spelling for indexed text and search queries.

The same Persian word reaches ParsRAG in several byte forms: Arabic Yeh and
Kaf (ي, ك) from Arabic keyboard layouts and PDF generators, presentation
forms from old PDFs, tatweel stretching, optional diacritics, and Arabic-Indic
digits. The embedding model treats each form as a different token, so a
question typed with Persian letters missed passages stored with Arabic ones.
Indexed text and questions are therefore mapped to one canonical spelling.
The mapping only replaces visually equivalent characters, so cited passages
still read the same.
"""

import re
import unicodedata

_LETTERS = str.maketrans(
    {
        "ي": "ی",  # Arabic Yeh -> Persian Yeh
        "ى": "ی",  # Alef Maksura -> Persian Yeh
        "ے": "ی",  # Yeh Barree -> Persian Yeh
        "ك": "ک",  # Arabic Kaf -> Keheh
        "ڪ": "ک",  # Swash Kaf -> Keheh
        "ـ": None,  # Tatweel (kashida)
        "​": None,  # Zero-width space
        "﻿": None,  # Byte-order mark
        **{chr(0x0660 + digit): chr(0x06F0 + digit) for digit in range(10)},
    }
)
# Harakat and Quranic marks (not hamza above, which writes Persian ezafe).
_DIACRITICS = re.compile(r"[ً-ٖٓ-ٰٟۖ-ۭ]")
_ARABIC_PRESENTATION_FORMS = re.compile(r"[ﭐ-﷿ﹰ-﻿]")
_REPEATED_ZWNJ = re.compile(r"‌{2,}")
_ZWNJ_AT_SPACE = re.compile(r" ?‌ ?(?=\s)|(?<=\s)‌")


def normalize_persian(text: str) -> str:
    """Return text with one canonical spelling for Persian letters and marks."""
    if not text:
        return text
    if _ARABIC_PRESENTATION_FORMS.search(text):
        # Old PDFs store contextual glyph forms (e.g. U+FEE3); NFKC maps them
        # back to base letters without touching ordinary Persian characters.
        text = _ARABIC_PRESENTATION_FORMS.sub(
            lambda match: unicodedata.normalize("NFKC", match.group(0)), text
        )
    text = text.translate(_LETTERS)
    text = _DIACRITICS.sub("", text)
    text = _REPEATED_ZWNJ.sub("‌", text)
    return _ZWNJ_AT_SPACE.sub("", text)
