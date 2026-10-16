"""A second, sparse-text OCR pass only adds what the first reading missed."""

from io import BytesIO
from unittest.mock import patch

from PIL import Image

from backend.infrastructure.parsers import ocr
from backend.infrastructure.parsers.ocr import (
    OCRSettings,
    extract_image_text,
    merge_readings,
)


def test_merge_keeps_the_first_reading_and_adds_only_new_lines() -> None:
    main = "اجرای آزمون‌ها\nتعداد کل تست ها"
    extra = "تعداد کل  تست‌ها\nپایان فرایند آزمون\nزمان سپری شده: 03:45\nx"
    assert merge_readings(main, extra) == (
        "اجرای آزمون‌ها\nتعداد کل تست ها\n\nپایان فرایند آزمون\nزمان سپری شده: 03:45"
    )
    assert merge_readings(main, "") == main
    assert merge_readings("", "voyage-code-3") == "voyage-code-3"


def _png(color: str) -> bytes:
    image = BytesIO()
    Image.new("RGB", (300, 120), color).save(image, format="PNG")
    return image.getvalue()


def test_dark_screenshots_are_inverted_for_the_sparse_pass() -> None:
    """Light text on a dark UI is read as dark text on light."""
    seen: list[float] = []

    def recognize(
        image: bytes, settings: OCRSettings, *, page_segmentation: str
    ) -> tuple[str, float]:
        if page_segmentation == "11":
            pixel = Image.open(BytesIO(image)).convert("L").getpixel((0, 0))
            seen.append(float(pixel) if isinstance(pixel, int | float) else 0.0)
            return "Embed voyage-code-3", 80.0
        return "Chat Codestral", 90.0

    settings = OCRSettings(True, "eng", 200, 30, 30)
    with patch.object(ocr, "_recognize", side_effect=recognize):
        text = extract_image_text(_png("#1e1e1e"), settings)

    assert text == "Chat Codestral\n\nEmbed voyage-code-3"
    assert seen and seen[0] > 200
