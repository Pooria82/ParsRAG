"""Logical-order extraction for right-to-left PDF text layers."""

from typing import Any

from backend.infrastructure.parsers.pdf_text import (
    logical_page_text,
    text_layer_is_garbled,
)

BASELINE = 40.0
HEIGHT = 12.0
WIDTH = 5.0
GAP = 3.0

Glyph = dict[str, Any]


def _glyph(character: str, x0: float) -> Glyph:
    return {
        "c": character,
        "bbox": (x0, BASELINE - HEIGHT, x0 + WIDTH, BASELINE),
        "origin": (x0, BASELINE),
    }


class VisualLine:
    """Lay out a visual line from right to left, like a Persian PDF page."""

    def __init__(self, right: float = 500.0) -> None:
        """Start the line at its right edge."""
        self.cursor = right
        self.glyphs: list[Glyph] = []

    def rtl(self, word: str, gap: float = GAP) -> "VisualLine":
        """Place an Arabic-script word; its first letter is rightmost."""
        for character in word:
            self.cursor -= WIDTH
            self.glyphs.append(_glyph(character, self.cursor))
        self.cursor -= gap
        return self

    def ltr(self, run: str, gap: float = GAP) -> "VisualLine":
        """Place an embedded Latin run or number, drawn left to right."""
        start = self.cursor - WIDTH * len(run)
        for index, character in enumerate(run):
            self.glyphs.append(_glyph(character, start + WIDTH * index))
        self.cursor = start - gap
        return self


class FakePage:
    """PyMuPDF page double exposing native text and rawdict glyphs."""

    def __init__(self, native: str, *lines: list[Glyph]) -> None:
        """Store the native text and one block of glyph lines."""
        self.native = native
        self.raw = {
            "blocks": [
                {"type": 0, "lines": [{"spans": [{"chars": line}]} for line in lines]}
            ]
        }

    def get_text(self, option: str, *, flags: int = 0) -> Any:
        """Return native text or the rawdict structure."""
        return self.native if option == "text" else self.raw


def test_visual_order_and_overlapping_spaces_become_logical_words() -> None:
    glyphs = VisualLine().rtl("تحلیل").rtl("کنید").glyphs
    # A space glyph drawn on top of the final letter must not split the word.
    last = glyphs[4]["bbox"]
    glyphs.append(
        {
            "c": " ",
            "bbox": (last[0] + 0.2, last[1], last[2], last[3]),
            "origin": (last[0], BASELINE),
        }
    )
    scrambled = glyphs[5:] + glyphs[:5]

    assert logical_page_text(FakePage("لی تحل دی کن", scrambled)) == "تحلیل کنید"


def test_embedded_latin_words_and_persian_numbers_keep_reading_order() -> None:
    line = VisualLine().rtl("پروتکل").ltr("SSL").rtl("نسخه").ltr("۱۵٫۵").glyphs

    assert logical_page_text(FakePage("پروتکل نسخه", line)) == "پروتکل SSL نسخه ۱۵٫۵"


def test_ezafe_hamza_stays_on_its_letter() -> None:
    """A zero-width mark on the boundary follows the letter drawn before it."""
    glyphs = [
        _glyph("ب", 515.0),
        _glyph("و", 510.0),
        _glyph("د", 505.0),
        _glyph("ج", 500.0),
        _glyph("ه", 495.0),
        {"c": "ٔ", "bbox": (500.0, 28.0, 500.0, 40.0), "origin": (500.0, BASELINE)},
    ]

    assert logical_page_text(FakePage("ﺑﻮﺩﺟٔﻪ", glyphs)) == "بودجهٔ"


def test_medial_lam_mapped_to_a_click_letter_is_repaired() -> None:
    line = VisualLine().rtl("میǁیون").glyphs
    assert logical_page_text(FakePage("ﻣﯿǁﯿﻮﻥ", line)) == "میلیون"


def test_mirrored_parentheses_are_restored() -> None:
    line = VisualLine().rtl("احراز").rtl(")", gap=0).ltr("TLS", gap=0).rtl("(").glyphs

    assert logical_page_text(FakePage("احراز", line)) == "احراز (TLS)"


def test_latin_heavy_line_in_a_persian_page_still_reads_right_to_left() -> None:
    line = VisualLine().rtl("نقش").ltr("SSL Handshake Protocol").glyphs
    page = FakePage("نقش پروتکل‌ها در این صفحهٔ فارسی بررسی می‌شود", line)

    assert logical_page_text(page) == "نقش SSL Handshake Protocol"


def test_latin_only_pages_keep_native_text() -> None:
    page = FakePage("Native English text\n", VisualLine().ltr("ignored").glyphs)

    assert logical_page_text(page) == "Native English text"


def test_non_dict_raw_output_falls_back_to_native_text() -> None:
    class StringPage:
        def get_text(self, option: str, *, flags: int = 0) -> Any:
            """Return plain text for every format."""
            return "متن فارسی"

    assert logical_page_text(StringPage()) == "متن فارسی"


def test_garbled_text_layers_are_detected() -> None:
    assert text_layer_is_garbled("" * 10 + "abc")
    assert text_layer_is_garbled("ÊÌåÇ ÈÑÇí ÊÓÊ ÇÓÊ " * 5)
    assert text_layer_is_garbled("متن خراب � " * 5)
    assert not text_layer_is_garbled("این یک متن فارسی سالم برای آزمون تشخیص است " * 2)
    assert not text_layer_is_garbled("Café déjà vu résumé naïve façade " * 3)
    assert not text_layer_is_garbled("کوتاه")
