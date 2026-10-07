"""Logical-order text extraction for PDF pages that contain right-to-left script.

Many Persian PDFs store glyphs in visual order, split words into separate runs,
or place space glyphs on top of letters. Reading the content stream as-is then
yields text such as "لی تحل دی کن" for "تحلیل کنید". For blocks that contain
Arabic-script letters, this module rebuilds each visual line from glyph
geometry: right-to-left lines are ordered by position, spaces come from real
gaps, and embedded Latin words and numbers are restored to reading order.
Pages and blocks without Arabic-script letters keep the parser's native text.
"""

import re
import unicodedata
from collections.abc import Sequence
from typing import Any, Protocol

import pymupdf

ARABIC_LETTER = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")
_LTR_RUN = re.compile(
    r"[A-Za-z0-9۰-۹٠-٩]"
    r"(?:[A-Za-z0-9۰-۹٠-٩.,:/_\-+%٫٬٪]|\s(?=[A-Za-z0-9]))*"
)
_PRIVATE_USE = re.compile(r"[-]")
_MOJIBAKE = re.compile(r"[À-ÿ]")
_BASELINE_TOLERANCE = 0.45
_WORD_GAP = 0.12
_MIRRORED_PAIRS = (("(", ")"), ("[", "]"))
# Some PDF writers map the medial Lam glyph of Naskh fonts to U+01C1 (ǁ),
# which has the same shape. That letter never occurs in Persian or Arabic.
_MISMAPPED_LAM = re.compile(
    r"(?<=[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF])\u01c1|\u01c1(?=[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFF])"
)

Glyph = dict[str, Any]


class TextPage(Protocol):
    """PDF page methods needed for logical-order extraction."""

    def get_text(self, option: str, *, flags: int = ...) -> Any:
        """Return text in the requested PyMuPDF format."""


def _glyph_size(glyph: Glyph) -> float:
    return max(1.0, float(glyph["bbox"][3]) - float(glyph["bbox"][1]))


def _visual_lines(glyphs: list[Glyph]) -> list[list[Glyph]]:
    """Group glyphs that share a baseline, top to bottom."""
    ordered = sorted(glyphs, key=lambda glyph: float(glyph["origin"][1]))
    lines: list[list[Glyph]] = []
    for glyph in ordered:
        if lines and abs(
            float(lines[-1][-1]["origin"][1]) - float(glyph["origin"][1])
        ) <= _BASELINE_TOLERANCE * _glyph_size(glyph):
            lines[-1].append(glyph)
        else:
            lines.append([glyph])
    return lines


def _repair_mirrored_brackets(line: str) -> str:
    """Swap brackets that a right-to-left run stored in mirrored form."""
    for opening, closing in _MIRRORED_PAIRS:
        first_open, first_close = line.find(opening), line.find(closing)
        if (
            first_close >= 0
            and (first_open < 0 or first_close < first_open)
            and line.count(opening) == line.count(closing)
        ):
            line = line.translate(str.maketrans(opening + closing, closing + opening))
    return line


def _clusters(glyphs: Sequence[Glyph]) -> list[list[Glyph]]:
    """Attach each combining mark to the glyph before it in content order.

    Marks such as the ezafe hamza (هٔ) are zero-width glyphs drawn on the edge
    between two letters, so their position cannot tell which letter they
    belong to; the content stream draws them right after their base letter.
    """
    clusters: list[list[Glyph]] = []
    for glyph in glyphs:
        character = str(glyph["c"])
        if character.isspace():
            continue
        if clusters and unicodedata.combining(character):
            clusters[-1].append(glyph)
        else:
            clusters.append([glyph])
    return clusters


def _right_to_left_line(glyphs: Sequence[Glyph]) -> str:
    """Order one right-to-left visual line and restore embedded LTR runs."""
    clusters = _clusters(glyphs)
    clusters.sort(
        key=lambda cluster: (
            (float(cluster[0]["bbox"][0]) + float(cluster[0]["bbox"][2])) / 2
        ),
        reverse=True,
    )
    parts: list[str] = []
    previous: Glyph | None = None
    for cluster in clusters:
        glyph = cluster[0]
        if previous is not None:
            gap = float(previous["bbox"][0]) - float(glyph["bbox"][2])
            if gap > _WORD_GAP * _glyph_size(glyph):
                parts.append(" ")
        parts.extend(str(item["c"]) for item in cluster)
        previous = glyph
    text = _LTR_RUN.sub(lambda match: match.group(0)[::-1], "".join(parts))
    text = _MISMAPPED_LAM.sub("ل", text)
    return _repair_mirrored_brackets(" ".join(text.split()))


def _left_to_right_line(glyphs: Sequence[Glyph]) -> str:
    """Order one left-to-right visual line, keeping the document's spaces."""
    ordered = sorted(glyphs, key=lambda glyph: float(glyph["bbox"][0]))
    return " ".join("".join(str(glyph["c"]) for glyph in ordered).split())


def _is_right_to_left(characters: str) -> bool:
    return len(ARABIC_LETTER.findall(characters)) >= len(
        _LATIN_LETTER.findall(characters)
    )


def _block_glyphs(block: dict[str, Any]) -> list[Glyph]:
    return [
        glyph
        for line in block.get("lines", [])
        for span in line.get("spans", [])
        for glyph in span.get("chars", [])
    ]


def _block_text(block: dict[str, Any], page_right_to_left: bool) -> str:
    """Rebuild a block line by line using the paragraph's base direction.

    As with the Unicode bidi paragraph level, a page or block whose letters are
    mostly Arabic script is right-to-left, so a Persian line dominated by an
    English term still reads right to left. Lines without Arabic letters are
    left-to-right.
    """
    glyphs = _block_glyphs(block)
    base_right_to_left = page_right_to_left or _is_right_to_left(
        "".join(str(glyph["c"]) for glyph in glyphs)
    )
    lines: list[str] = []
    for visual_line in _visual_lines(glyphs):
        characters = "".join(str(glyph["c"]) for glyph in visual_line)
        right_to_left = bool(ARABIC_LETTER.search(characters)) and (
            base_right_to_left or _is_right_to_left(characters)
        )
        text = (
            _right_to_left_line(visual_line)
            if right_to_left
            else _left_to_right_line(visual_line)
        )
        if text:
            lines.append(text)
    return "\n".join(lines)


def _native_block_text(block: dict[str, Any]) -> str:
    """Join a block's glyphs in content-stream order, line by line."""
    return "\n".join(
        "".join(
            str(glyph["c"])
            for span in line.get("spans", [])
            for glyph in span.get("chars", [])
        ).strip()
        for line in block.get("lines", [])
    ).strip()


def logical_page_text(page: TextPage) -> str:
    """Return a page's text in reading order, rebuilding right-to-left blocks.

    Pages without Arabic-script letters return the parser's native text
    unchanged, so Latin-only documents are never affected.
    """
    native = str(page.get_text("text"))
    if not ARABIC_LETTER.search(native):
        return native.strip()
    raw = page.get_text("rawdict", flags=pymupdf.TEXTFLAGS_TEXT)
    blocks = raw.get("blocks") if isinstance(raw, dict) else None
    if not isinstance(blocks, list):
        return native.strip()
    page_right_to_left = _is_right_to_left(native)
    texts: list[str] = []
    for block in blocks:
        if not isinstance(block, dict) or block.get("type") != 0:
            continue
        stream_text = _native_block_text(block)
        rebuilt = (
            _block_text(block, page_right_to_left)
            if ARABIC_LETTER.search(stream_text)
            else stream_text
        )
        if rebuilt:
            texts.append(rebuilt)
    return "\n\n".join(texts).strip()


def text_layer_is_garbled(text: str) -> bool:
    """Detect text layers whose fonts lack a usable Unicode mapping.

    Broken Persian PDFs typically extract as private-use code points or as
    Latin-1 mojibake (for example "ÊÌåÇ"). Such pages should be read by OCR.
    """
    private = len(_PRIVATE_USE.findall(text))
    letters = sum(1 for character in text if character.isalpha()) + private
    if letters < 20:
        return False
    if "\N{REPLACEMENT CHARACTER}" in text or private / letters > 0.05:
        return True
    mojibake = len(_MOJIBAKE.findall(text))
    arabic = len(ARABIC_LETTER.findall(text))
    return arabic == 0 and mojibake / letters > 0.3
