"""Sideways, upside-down, and skewed scans are re-read upright."""

import subprocess
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from backend.infrastructure.parsers import ocr
from backend.infrastructure.parsers.ocr import OCRSettings

SETTINGS = OCRSettings(True, "fas+eng", 200, 12, 5, correct_orientation=True)


def _lines_page(angle: float = 0.0) -> Image.Image:
    """A white page with horizontal text-like bars, optionally rotated."""
    page = Image.new("L", (600, 800), 255)
    draw = ImageDraw.Draw(page)
    for top in range(60, 740, 40):
        draw.rectangle((60, top, 540, top + 12), fill=0)
    return page.rotate(angle, expand=True, fillcolor=255) if angle else page


def _png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize("angle", [0.0, 3.0, -5.0, 6.5])
def test_skew_is_measured_from_text_lines(angle: float) -> None:
    assert ocr._skew_angle(_lines_page(angle)) == pytest.approx(-angle, abs=0.3)


def test_blank_pages_have_no_skew() -> None:
    assert ocr._skew_angle(Image.new("L", (300, 300), 255)) == 0.0


@pytest.mark.parametrize(
    ("output", "returncode", "expected"),
    [
        ("Page number: 0\nRotate: 90\nOrientation confidence: 7.2\n", 0, 90),
        ("Rotate: 180\nOrientation confidence: 0.4\n", 0, 0),
        ("Rotate: 0\nOrientation confidence: 9.0\n", 0, 0),
        ("Too few characters. Skipping this page\n", 1, 0),
    ],
)
def test_orientation_needs_a_confident_detection(
    output: str, returncode: int, expected: int
) -> None:
    result = subprocess.CompletedProcess([], returncode, output.encode(), b"")
    with patch(
        "backend.infrastructure.parsers.ocr.subprocess.run", return_value=result
    ):
        assert ocr._orientation(b"png", SETTINGS) == expected


def test_missing_orientation_model_leaves_the_page_alone() -> None:
    with patch(
        "backend.infrastructure.parsers.ocr.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        assert ocr._orientation(b"png", SETTINGS) == 0


def test_a_sideways_page_is_rotated_and_read_again() -> None:
    reads = iter([("نامفهوم", 30.0), ("متن درست صفحه", 91.0)])
    with (
        patch.object(ocr, "_read", side_effect=lambda image, settings: next(reads)),
        patch.object(ocr, "_orientation", return_value=90) as orientation,
        patch.object(ocr, "_skew_angle", return_value=0.0),
    ):
        text = ocr._run_tesseract(_png(_lines_page()), SETTINGS)

    assert text == "متن درست صفحه"
    orientation.assert_called_once()


def test_confident_upright_pages_skip_orientation_detection() -> None:
    with (
        patch.object(ocr, "_read", return_value=("متن", 90.0)) as read,
        patch.object(ocr, "_orientation") as orientation,
        patch.object(ocr, "_skew_angle", return_value=0.5),
    ):
        assert ocr._run_tesseract(_png(_lines_page()), SETTINGS) == "متن"

    orientation.assert_not_called()
    read.assert_called_once()


@pytest.mark.parametrize(
    ("deskewed_confidence", "expected"), [(86.0, "صاف"), (81.0, "کج")]
)
def test_deskewed_reading_must_be_clearly_more_confident(
    deskewed_confidence: float, expected: str
) -> None:
    reads = iter([("کج", 80.0), ("صاف", deskewed_confidence)])
    with (
        patch.object(ocr, "_read", side_effect=lambda image, settings: next(reads)),
        patch.object(ocr, "_skew_angle", return_value=5.0),
    ):
        assert ocr._run_tesseract(_png(_lines_page()), SETTINGS) == expected


def test_correction_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCR_ORIENTATION", "0")
    settings = OCRSettings.from_environment()
    assert not settings.correct_orientation
    with (
        patch.object(ocr, "_read", return_value=("متن", 10.0)),
        patch.object(ocr, "_orientation") as orientation,
    ):
        ocr._run_tesseract(b"png", settings)
    orientation.assert_not_called()
    monkeypatch.delenv("OCR_ORIENTATION")
    assert OCRSettings.from_environment().correct_orientation
