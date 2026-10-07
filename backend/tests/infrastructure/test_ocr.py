"""Tests for the bounded Tesseract OCR infrastructure adapter."""

import subprocess
from io import BytesIO
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from PIL import Image

from backend.infrastructure.parsers.ocr import (
    OCRSettings,
    OCRTimeoutError,
    OCRUnavailableError,
    extract_image_text,
    extract_page_text,
    normalize_ocr_text,
)

TSV_HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop"
    "\twidth\theight\tconf\ttext"
)


def tsv(*words: tuple[int, int, int, float, str]) -> bytes:
    """Build Tesseract TSV for (block, paragraph, line, confidence, word) rows."""
    rows = [TSV_HEADER]
    for index, (block, paragraph, line, confidence, word) in enumerate(words, 1):
        rows.append(
            f"5\t1\t{block}\t{paragraph}\t{line}\t{index}\t0\t0\t10\t10"
            f"\t{confidence}\t{word}"
        )
    return "\n".join(rows).encode()


def completed(stdout: bytes) -> subprocess.CompletedProcess[bytes]:
    """Wrap Tesseract output in a successful process result."""
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr=b"")


def test_ocr_settings_are_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid or excessive environment settings resolve to safe values."""
    monkeypatch.setenv("OCR_ENABLED", "yes")
    monkeypatch.setenv("OCR_DPI", "9999")
    monkeypatch.setenv("OCR_TIMEOUT_SECONDS", "invalid")
    monkeypatch.setenv("OCR_MAX_PAGES", "0")

    settings = OCRSettings.from_environment()

    assert settings.enabled is True
    assert settings.dpi == 600
    assert settings.timeout_seconds == 45
    assert settings.max_pages == 1


def test_ocr_text_normalization_preserves_paragraphs() -> None:
    """OCR whitespace is cleaned without flattening paragraph boundaries."""
    assert normalize_ocr_text("  خط   اول\n\n خط دوم \f") == "خط اول\n\nخط دوم"


@patch("backend.infrastructure.parsers.ocr.subprocess.run")
def test_extract_page_text_invokes_tesseract(mock_run: MagicMock) -> None:
    """The adapter sends an in-memory PNG to Tesseract without temp files."""
    page = MagicMock()
    page.rect.width = 612
    page.rect.height = 792
    page.get_pixmap.return_value.tobytes.return_value = b"png"
    mock_run.return_value = completed(
        tsv((1, 1, 1, 91.0, "\u200fمتن\u200f"), (1, 1, 1, 90.0, "اسکن‌شده"))
    )
    settings = OCRSettings(True, "fas+eng", 300, 12, 5)

    result = extract_page_text(page, settings)

    assert result == "متن اسکن‌شده"
    assert mock_run.call_args.kwargs["input"] == b"png"
    assert mock_run.call_args.kwargs["timeout"] == 12
    assert mock_run.call_args.args[0][:3] == ["tesseract", "stdin", "stdout"]
    assert "--oem" in mock_run.call_args.args[0]
    assert mock_run.call_count == 1


@patch(
    "backend.infrastructure.parsers.ocr.subprocess.run", side_effect=FileNotFoundError
)
def test_missing_tesseract_has_specific_error(mock_run: MagicMock) -> None:
    """Missing system OCR is distinguished from an invalid document."""
    page = MagicMock()
    page.rect.width = 612
    page.rect.height = 792
    page.get_pixmap.return_value.tobytes.return_value = b"png"

    with pytest.raises(OCRUnavailableError, match="not installed"):
        extract_page_text(page, OCRSettings(True, "fas+eng", 300, 10, 1))


@patch(
    "backend.infrastructure.parsers.ocr.subprocess.run",
    side_effect=subprocess.TimeoutExpired(cmd="tesseract", timeout=1),
)
def test_tesseract_timeout_has_specific_error(mock_run: MagicMock) -> None:
    """A stalled OCR process cannot block ingestion indefinitely."""
    page = MagicMock()
    page.rect.width = 612
    page.rect.height = 792
    page.get_pixmap.return_value.tobytes.return_value = b"png"

    with pytest.raises(OCRTimeoutError, match="timed out"):
        extract_page_text(page, OCRSettings(True, "fas+eng", 300, 1, 1))


@patch("backend.infrastructure.parsers.ocr.subprocess.run")
def test_extract_image_text_validates_and_normalizes_raster(
    mock_run: MagicMock,
) -> None:
    """Standalone and embedded images are normalized before Tesseract runs."""
    source = BytesIO()
    Image.new("RGB", (640, 480), "white").save(source, format="JPEG")
    mock_run.return_value = completed(
        tsv((1, 1, 1, 88.0, "متن"), (1, 1, 1, 87.0, "تصویر"))
    )

    result = extract_image_text(
        source.getvalue(), OCRSettings(True, "fas+eng", 300, 12, 5)
    )

    assert result == "متن تصویر"
    assert mock_run.call_args.kwargs["input"].startswith(b"\x89PNG")
    with Image.open(BytesIO(mock_run.call_args.kwargs["input"])) as normalized:
        assert normalized.size == (1280, 960)
        assert normalized.mode == "L"


def test_extract_image_text_rejects_invalid_raster() -> None:
    """Forged image extensions cannot send arbitrary bytes to Tesseract."""
    with pytest.raises(ValueError, match="valid image"):
        extract_image_text(b"not-an-image", OCRSettings(True, "fas+eng", 300, 12, 5))


def test_pdf_ocr_rejects_oversized_page_before_rasterization() -> None:
    """A large PDF page cannot allocate a Pixmap beyond the pixel budget."""
    page = MagicMock()
    page.rect.width = 20_000
    page.rect.height = 20_000
    with pytest.raises(ValueError, match="OCR pixel limit"):
        extract_page_text(page, OCRSettings(True, "fas+eng", 600, 12, 5))
    page.get_pixmap.assert_not_called()


@patch("backend.infrastructure.parsers.ocr.subprocess.run")
def test_uncertain_pages_are_reread_as_one_block(mock_run: MagicMock) -> None:
    """A dropped-line first pass is replaced by a more confident block pass."""
    page = MagicMock()
    page.rect.width = 612
    page.rect.height = 792
    page.get_pixmap.return_value.tobytes.return_value = b"png"
    mock_run.side_effect = [
        completed(tsv((1, 1, 1, 40.0, "ناقص"))),
        completed(
            tsv(
                (1, 1, 1, 92.0, "سطر"),
                (1, 1, 1, 92.0, "اول"),
                (1, 1, 2, 90.0, "سطر"),
                (1, 1, 2, 90.0, "دوم"),
            )
        ),
    ]

    result = extract_page_text(page, OCRSettings(True, "fas+eng", 300, 12, 5))

    assert result == "سطر اول\nسطر دوم"
    assert [
        call.args[0][call.args[0].index("--psm") + 1]
        for call in mock_run.call_args_list
    ] == ["3", "6"]


@patch("backend.infrastructure.parsers.ocr.subprocess.run")
def test_confident_first_pass_wins_over_weaker_block_pass(mock_run: MagicMock) -> None:
    """The block pass replaces the first reading only when it is more confident."""
    page = MagicMock()
    page.rect.width = 612
    page.rect.height = 792
    page.get_pixmap.return_value.tobytes.return_value = b"png"
    mock_run.side_effect = [
        completed(tsv((1, 1, 1, 70.0, "خواندن"), (2, 1, 1, 70.0, "دوم"))),
        completed(tsv((1, 1, 1, 30.0, "خراب"))),
    ]

    result = extract_page_text(page, OCRSettings(True, "fas+eng", 300, 12, 5))

    assert result == "خواندن\n\nدوم"


def test_bidi_controls_are_removed_from_ocr_text() -> None:
    """Invisible direction marks never reach chunks or embeddings."""
    assert normalize_ocr_text("\u200eGL\u200f متن\u061c") == "GL متن"


def test_page_rasters_are_grayscale_without_contrast_stretching() -> None:
    """PDF pages reach Tesseract as grayscale renders, unmodified."""
    page = MagicMock()
    page.rect.width = 612
    page.rect.height = 792
    page.get_pixmap.return_value.tobytes.return_value = b"png"
    with patch("backend.infrastructure.parsers.ocr.subprocess.run") as run:
        run.return_value = completed(tsv((1, 1, 1, 95.0, "متن")))
        extract_page_text(page, OCRSettings(True, "fas+eng", 200, 12, 5))

    assert page.get_pixmap.call_args.kwargs["colorspace"] is pymupdf.csGRAY
    assert run.call_args.kwargs["input"] == b"png"
