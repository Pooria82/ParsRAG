"""Bounded Tesseract OCR adapter for scanned PDF pages."""

import os
import re
import statistics
import subprocess
from dataclasses import dataclass
from io import BytesIO
from math import ceil, isfinite
from typing import Protocol

import numpy as np
import pymupdf
from PIL import Image, ImageOps, UnidentifiedImageError


class PixmapLike(Protocol):
    """Minimal PyMuPDF pixmap boundary used by the OCR adapter."""

    def tobytes(self, output: str) -> bytes:
        """Serializes the rendered page."""


class RasterizablePage(Protocol):
    """Minimal PDF page boundary required for rasterization."""

    rect: object

    def get_pixmap(self, *, dpi: int, colorspace: object, alpha: bool) -> PixmapLike:
        """Renders the page into a pixel map."""


class OCRError(ValueError):
    """Base error for deterministic OCR failures."""


class OCRUnavailableError(OCRError):
    """Raised when the Tesseract executable is unavailable."""


class OCRTimeoutError(OCRError):
    """Raised when one OCR page exceeds its time budget."""


class OCRPageLimitError(OCRError):
    """Raised when a document contains too many scanned pages."""


class OCRImageLimitError(OCRError):
    """Raised when a document contains too many images requiring OCR."""


# Tesseract marks right-to-left words with invisible bidi controls; they would
# otherwise end up in chunks, embeddings, and lexical matching.
_BIDI_CONTROLS = dict.fromkeys(
    map(ord, "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
)
# Below this mean word confidence the page is re-read as one uniform block,
# which recovers lines that automatic layout analysis drops on Persian pages.
_CONFIDENT_RECOGNITION = 75.0
# Skews below this are handled by Tesseract itself; a deskewed reading must
# also be this much more confident, since rotating again blurs the glyphs.
_MIN_DESKEW_DEGREES = 2.0
_DESKEW_CONFIDENCE_GAIN = 3.0
_MIN_ORIENTATION_CONFIDENCE = 1.5
_TESSERACT_OPTIONS = (
    "--oem",
    "1",
    "-c",
    "preserve_interword_spaces=1",
    "-c",
    "tessedit_create_tsv=1",
)


def _environment_int(name: str, default: int, minimum: int, maximum: int) -> int:
    """Reads a bounded integer setting and falls back safely."""
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return min(maximum, max(minimum, value))


@dataclass(frozen=True)
class OCRSettings:
    """Runtime limits for Tesseract OCR."""

    enabled: bool
    languages: str
    dpi: int
    timeout_seconds: int
    max_pages: int
    max_images: int = 30
    max_image_pixels: int = 40_000_000
    min_image_pixels: int = 10_000
    correct_orientation: bool = False

    @classmethod
    def from_environment(cls) -> "OCRSettings":
        """Builds validated OCR settings from environment variables."""
        return cls(
            enabled=os.getenv("OCR_ENABLED", "0").strip().lower()
            in {"1", "true", "yes", "on"},
            languages=os.getenv("OCR_LANGUAGES", "fas+eng").strip() or "fas+eng",
            dpi=_environment_int("OCR_DPI", 200, 150, 600),
            timeout_seconds=_environment_int("OCR_TIMEOUT_SECONDS", 45, 1, 300),
            max_pages=_environment_int("OCR_MAX_PAGES", 30, 1, 200),
            max_images=_environment_int("OCR_MAX_IMAGES", 30, 1, 500),
            max_image_pixels=_environment_int(
                "OCR_MAX_IMAGE_PIXELS", 40_000_000, 1_000_000, 200_000_000
            ),
            min_image_pixels=_environment_int(
                "OCR_MIN_IMAGE_PIXELS", 10_000, 1, 1_000_000
            ),
            correct_orientation=os.getenv("OCR_ORIENTATION", "1").strip().lower()
            not in {"0", "false", "no", "off"},
        )


def normalize_ocr_text(value: str) -> str:
    """Normalizes OCR whitespace and bidi marks while preserving paragraphs."""
    cleaned = value.replace("\f", "").translate(_BIDI_CONTROLS)
    lines = [" ".join(line.split()) for line in cleaned.splitlines()]
    normalized: list[str] = []
    for line in lines:
        if line:
            normalized.append(line)
        elif normalized and normalized[-1]:
            normalized.append("")
    return "\n".join(normalized).strip()


def extract_page_text(
    page: RasterizablePage, settings: OCRSettings | None = None
) -> str:
    """Runs Tesseract on one rendered PDF page.

    Args:
        page: Rasterizable PDF page supplied by PyMuPDF.
        settings: Optional validated runtime settings.

    Returns:
        Normalized OCR text, or an empty string when no text is recognized.

    Raises:
        OCRUnavailableError: If Tesseract is not installed.
        OCRTimeoutError: If recognition exceeds the configured timeout.
        OCRError: If Tesseract returns a non-zero exit status.
    """
    active = settings or OCRSettings.from_environment()
    width = float(page.rect.width)  # type: ignore[attr-defined]
    height = float(page.rect.height)  # type: ignore[attr-defined]
    if not isfinite(width) or not isfinite(height) or width <= 0 or height <= 0:
        raise OCRError("The PDF page dimensions are invalid for OCR.")
    pixels = ceil(width * active.dpi / 72) * ceil(height * active.dpi / 72)
    if pixels > active.max_image_pixels:
        raise OCRError("The PDF page exceeds the configured OCR pixel limit.")
    pixmap = page.get_pixmap(dpi=active.dpi, colorspace=pymupdf.csGRAY, alpha=False)
    # Tesseract binarizes internally; contrast stretching before it erased
    # whole Persian pages in benchmarks, so only grayscale is applied.
    return _run_tesseract(pixmap.tobytes("png"), active)


def _tsv_text(output: str) -> tuple[str, float]:
    """Rebuild reading-order text and mean word confidence from Tesseract TSV."""
    paragraphs: list[list[str]] = []
    words: list[str] = []
    confidences: list[float] = []
    line_key: tuple[str, ...] | None = None
    paragraph_key: tuple[str, ...] | None = None
    for row in output.splitlines()[1:]:
        columns = row.split("\t")
        if len(columns) < 12 or columns[0] != "5" or not columns[11].strip():
            continue
        if columns[1:5] != list(line_key or ()) and words:
            paragraphs[-1].append(" ".join(words))
            words = []
        if tuple(columns[1:4]) != paragraph_key:
            paragraphs.append([])
            paragraph_key = tuple(columns[1:4])
        line_key = tuple(columns[1:5])
        words.append(columns[11])
        try:
            confidences.append(float(columns[10]))
        except ValueError:
            continue
    if words:
        paragraphs[-1].append(" ".join(words))
    text = "\n\n".join("\n".join(lines) for lines in paragraphs if lines)
    return text, statistics.fmean(confidences) if confidences else 0.0


def _run_tesseract(image: bytes, settings: OCRSettings) -> str:
    """Recognize a page, correcting its orientation and skew when that helps."""
    text, confidence = _read(image, settings)
    if settings.correct_orientation:
        text, confidence = _correct_geometry(image, settings, text, confidence)
    return normalize_ocr_text(text)


def _read(image: bytes, settings: OCRSettings) -> tuple[str, float]:
    """Recognize a page, re-reading it as one block when layout analysis fails.

    Automatic page segmentation can drop whole lines of Persian text. When the
    first pass is empty or uncertain, a single-block pass runs and the more
    confident reading wins.
    """
    text, confidence = _recognize(image, settings, page_segmentation="3")
    if not text or confidence < _CONFIDENT_RECOGNITION:
        block_text, block_confidence = _recognize(
            image, settings, page_segmentation="6"
        )
        if block_text and (not text or block_confidence > confidence):
            return block_text, block_confidence
    return text, confidence


def _correct_geometry(
    image: bytes, settings: OCRSettings, text: str, confidence: float
) -> tuple[str, float]:
    """Re-read pages scanned sideways, upside down, or visibly skewed.

    On rendered Persian scans, character error fell from 0.85 to 0.09 for
    pages rotated 90 degrees and from 0.40 to 0.24 for pages skewed 5
    degrees, with upright pages unchanged. Orientation detection runs only
    for weak readings; a deskewed reading must be clearly more confident,
    because Tesseract already copes with small skews.
    """
    try:
        source = Image.open(BytesIO(image))
        source.load()
    except (UnidentifiedImageError, OSError):
        return text, confidence
    page: Image.Image = ImageOps.grayscale(source)
    best = (text, confidence)
    if not text or confidence < _CONFIDENT_RECOGNITION:
        rotation = _orientation(image, settings)
        if rotation:
            page = page.rotate(-rotation, expand=True, fillcolor=255)
            upright = _read(_png(page), settings)
            if upright[0] and (not best[0] or upright[1] > best[1]):
                best = upright
    angle = _skew_angle(page)
    if abs(angle) >= _MIN_DESKEW_DEGREES:
        straight = page.rotate(
            angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255
        )
        deskewed = _read(_png(straight), settings)
        if deskewed[0] and deskewed[1] >= best[1] + _DESKEW_CONFIDENCE_GAIN:
            best = deskewed
    return best


def _png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _orientation(image: bytes, settings: OCRSettings) -> int:
    """Clockwise degrees (90/180/270) that make the page upright, or 0.

    Uses Tesseract's orientation and script detection; without its model or
    with low confidence the page is left as it is.
    """
    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "--psm", "0", "-l", "osd"],
            input=image,
            capture_output=True,
            check=False,
            timeout=settings.timeout_seconds,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return 0
    output = result.stdout.decode("utf-8", errors="replace")
    rotate = re.search(r"Rotate:\s*(\d+)", output)
    certainty = re.search(r"Orientation confidence:\s*([\d.]+)", output)
    if result.returncode != 0 or rotate is None or certainty is None:
        return 0
    degrees = int(rotate.group(1)) % 360
    if degrees not in {90, 180, 270}:
        return 0
    return degrees if float(certainty.group(1)) >= _MIN_ORIENTATION_CONFIDENCE else 0


def _skew_angle(page: Image.Image) -> float:
    """Estimate text-line skew (degrees) by maximizing row-projection variance."""
    small = page.copy()
    small.thumbnail((700, 990))
    ink = Image.fromarray((np.asarray(small) < 128).astype(np.uint8) * 255)
    if not np.asarray(ink).any():
        return 0.0

    def sharpness(angle: float) -> float:
        rotated = ink.rotate(angle, resample=Image.Resampling.NEAREST, fillcolor=0)
        return float(np.var(np.asarray(rotated, dtype=np.float32).sum(axis=1)))

    coarse = max(np.arange(-8.0, 8.01, 1.0), key=sharpness)
    return float(max(np.arange(coarse - 0.75, coarse + 0.76, 0.25), key=sharpness))


def _recognize(
    image: bytes, settings: OCRSettings, *, page_segmentation: str
) -> tuple[str, float]:
    """Run one bounded Tesseract pass and return text with mean confidence."""
    command = [
        "tesseract",
        "stdin",
        "stdout",
        "-l",
        settings.languages,
        "--dpi",
        str(settings.dpi),
        "--psm",
        page_segmentation,
        *_TESSERACT_OPTIONS,
    ]
    try:
        result = subprocess.run(
            command,
            input=image,
            capture_output=True,
            check=False,
            timeout=settings.timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise OCRUnavailableError("Tesseract OCR is not installed.") from exc
    except subprocess.TimeoutExpired as exc:
        raise OCRTimeoutError(
            "Tesseract OCR timed out while processing a page."
        ) from exc
    if result.returncode != 0:
        raise OCRError("Tesseract OCR could not process the image.")
    return _tsv_text(result.stdout.decode("utf-8", errors="replace"))


def extract_image_text(image_bytes: bytes, settings: OCRSettings | None = None) -> str:
    """Validate, normalize, and OCR a standalone or embedded raster image."""
    active = settings or OCRSettings.from_environment()
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            width, height = source.size
            pixels = width * height
            if pixels > active.max_image_pixels:
                raise OCRError("The image exceeds the configured OCR pixel limit.")
            if pixels < active.min_image_pixels:
                return ""
            oriented = ImageOps.exif_transpose(source)
            if oriented.mode in {"RGBA", "LA"} or "transparency" in oriented.info:
                rgba = oriented.convert("RGBA")
                background = Image.new("RGBA", rgba.size, "white")
                background.alpha_composite(rgba)
                normalized = background.convert("L")
            else:
                normalized = oriented.convert("L")
            if normalized.width < 1200 and pixels * 4 <= active.max_image_pixels:
                normalized = normalized.resize(
                    (normalized.width * 2, normalized.height * 2),
                    Image.Resampling.LANCZOS,
                )
            output = BytesIO()
            normalized.save(output, format="PNG", optimize=True)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("The file is not a valid image.") from exc
    return _run_tesseract(output.getvalue(), active)
