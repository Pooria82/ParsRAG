"""Canonical Persian spelling for indexing and questions."""

import pytest

from backend.core.service.text_normalization import normalize_persian


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("كتاب علمي", "کتاب علمی"),  # Arabic Kaf and Yeh
        ("موسى", "موسی"),  # Alef Maksura
        ("بـــزرگ", "بزرگ"),  # tatweel
        ("كِتَابٌ", "کتاب"),  # diacritics
        ("سال ١٤٠٢", "سال ۱۴۰۲"),  # Arabic-Indic digits to Persian
        ("می‌‌خواهم", "می‌خواهم"),  # repeated ZWNJ
        ("کتاب‌ ها", "کتاب ها"),  # ZWNJ before a space
        ("ﻣﻦ", "من"),  # presentation forms from old PDFs
        ("zero​width", "zerowidth"),
    ],
)
def test_visually_equivalent_forms_share_one_spelling(raw: str, expected: str) -> None:
    assert normalize_persian(raw) == expected


def test_canonical_text_and_other_scripts_are_unchanged() -> None:
    text = "پژوهش‌های ۱۴۰۲ درباره GPU و C++ (نسخهٔ ۳.۱)"
    assert normalize_persian(text) == text
    assert normalize_persian("") == ""
    assert normalize_persian("ﻻ") == "لا"
