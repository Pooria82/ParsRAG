"""Tests for the bounded Tesseract OCR infrastructure adapter."""

import subprocess
from io import BytesIO
from unittest.mock import MagicMock, patch

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
    page.get_pixmap.return_value.tobytes.return_value = b"png"
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="متن  اسکن‌شده\n".encode(), stderr=b""
    )
    settings = OCRSettings(True, "fas+eng", 300, 12, 5)

    result = extract_page_text(page, settings)

    assert result == "متن اسکن‌شده"
    assert mock_run.call_args.kwargs["input"] == b"png"
    assert mock_run.call_args.kwargs["timeout"] == 12
    assert mock_run.call_args.args[0][:3] == ["tesseract", "stdin", "stdout"]


@patch(
    "backend.infrastructure.parsers.ocr.subprocess.run", side_effect=FileNotFoundError
)
def test_missing_tesseract_has_specific_error(mock_run: MagicMock) -> None:
    """Missing system OCR is distinguished from an invalid document."""
    page = MagicMock()
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
    mock_run.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout=" متن تصویر ".encode(), stderr=b""
    )

    result = extract_image_text(
        source.getvalue(), OCRSettings(True, "fas+eng", 300, 12, 5)
    )

    assert result == "متن تصویر"
    assert mock_run.call_args.kwargs["input"].startswith(b"\x89PNG")


def test_extract_image_text_rejects_invalid_raster() -> None:
    """Forged image extensions cannot send arbitrary bytes to Tesseract."""
    with pytest.raises(ValueError, match="valid image"):
        extract_image_text(b"not-an-image", OCRSettings(True, "fas+eng", 300, 12, 5))
