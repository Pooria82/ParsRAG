"""Bounded Tesseract OCR adapter for scanned PDF pages."""

import os
import subprocess
from dataclasses import dataclass
from typing import Protocol

import fitz  # type: ignore  # PyMuPDF has no complete type information.


class PixmapLike(Protocol):
    """Minimal PyMuPDF pixmap boundary used by the OCR adapter."""

    def tobytes(self, output: str) -> bytes:
        """Serializes the rendered page."""


class RasterizablePage(Protocol):
    """Minimal PDF page boundary required for rasterization."""

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

    @classmethod
    def from_environment(cls) -> "OCRSettings":
        """Builds validated OCR settings from environment variables."""
        return cls(
            enabled=os.getenv("OCR_ENABLED", "0").strip().lower()
            in {"1", "true", "yes", "on"},
            languages=os.getenv("OCR_LANGUAGES", "fas+eng").strip() or "fas+eng",
            dpi=_environment_int("OCR_DPI", 300, 150, 600),
            timeout_seconds=_environment_int("OCR_TIMEOUT_SECONDS", 45, 1, 300),
            max_pages=_environment_int("OCR_MAX_PAGES", 30, 1, 200),
        )


def normalize_ocr_text(value: str) -> str:
    """Normalizes OCR whitespace while preserving paragraph boundaries."""
    lines = [" ".join(line.split()) for line in value.replace("\f", "").splitlines()]
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
    pixmap = page.get_pixmap(dpi=active.dpi, colorspace=fitz.csRGB, alpha=False)
    image = pixmap.tobytes("png")
    command = [
        "tesseract",
        "stdin",
        "stdout",
        "-l",
        active.languages,
        "--dpi",
        str(active.dpi),
    ]
    try:
        result = subprocess.run(
            command,
            input=image,
            capture_output=True,
            check=False,
            timeout=active.timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise OCRUnavailableError("Tesseract OCR is not installed.") from exc
    except subprocess.TimeoutExpired as exc:
        raise OCRTimeoutError(
            "Tesseract OCR timed out while processing a page."
        ) from exc
    if result.returncode != 0:
        raise OCRError("Tesseract OCR could not process the scanned page.")
    return normalize_ocr_text(result.stdout.decode("utf-8", errors="replace"))
