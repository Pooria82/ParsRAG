import json
import os
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from docx import Document
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from backend.infrastructure.parsers.chunker import chunk_text
from backend.infrastructure.parsers.document_parser import (
    EmptyDocumentError,
    ParsedSection,
    parse_document,
    parse_document_sections,
)


@patch("backend.infrastructure.parsers.document_parser.fitz.open")
def test_parse_empty_pdf(mock_fitz_open: MagicMock) -> None:
    # Mock a PDF document with one page but no text
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = ""

    # Doc behaves like an iterator of pages
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz_open.return_value = mock_doc

    with pytest.raises(EmptyDocumentError, match="Scanned PDFs require OCR"):
        parse_document(b"fake pdf bytes", "fake.pdf")

    mock_doc.close.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.fitz.open")
def test_pdf_sections_keep_page_numbers(mock_fitz_open: MagicMock) -> None:
    mock_doc = MagicMock()
    first, second = MagicMock(), MagicMock()
    first.get_text.return_value = "first page"
    second.get_text.return_value = "second page"
    mock_doc.__iter__.return_value = [first, second]
    mock_fitz_open.return_value = mock_doc

    sections = parse_document_sections(b"pdf", "guide.pdf")

    assert [section.metadata for section in sections] == [{"page": 1}, {"page": 2}]
    mock_doc.close.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.extract_page_text")
@patch("backend.infrastructure.parsers.document_parser.fitz.open")
def test_scanned_pdf_uses_ocr_when_enabled(
    mock_fitz_open: MagicMock,
    mock_extract_page_text: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fully scanned PDFs use OCR and preserve their page citation."""
    monkeypatch.setenv("OCR_ENABLED", "1")
    page = MagicMock()
    page.get_text.return_value = ""
    document = MagicMock()
    document.__iter__.return_value = [page]
    mock_fitz_open.return_value = document
    mock_extract_page_text.return_value = "متن فارسی اسکن‌شده"

    sections = parse_document_sections(b"pdf", "scan.pdf")

    assert sections[0].text == "متن فارسی اسکن‌شده"
    assert sections[0].metadata == {"page": 1}
    mock_extract_page_text.assert_called_once()
    document.close.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.extract_page_text")
@patch("backend.infrastructure.parsers.document_parser.fitz.open")
def test_mixed_pdf_only_ocrs_scanned_pages(
    mock_fitz_open: MagicMock,
    mock_extract_page_text: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Native PDF pages remain the fast path in mixed documents."""
    monkeypatch.setenv("OCR_ENABLED", "true")
    native, scanned = MagicMock(), MagicMock()
    native.get_text.return_value = "native text"
    scanned.get_text.return_value = ""
    document = MagicMock()
    document.__iter__.return_value = [native, scanned]
    mock_fitz_open.return_value = document
    mock_extract_page_text.return_value = "ocr text"

    sections = parse_document_sections(b"pdf", "mixed.pdf")

    assert [(item.text, item.metadata) for item in sections] == [
        ("native text", {"page": 1}),
        ("ocr text", {"page": 2}),
    ]
    mock_extract_page_text.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.extract_page_text")
@patch("backend.infrastructure.parsers.document_parser.fitz.open")
def test_pdf_ocr_page_limit_is_enforced(
    mock_fitz_open: MagicMock,
    mock_extract_page_text: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OCR work is bounded independently from the upload byte limit."""
    monkeypatch.setenv("OCR_ENABLED", "1")
    monkeypatch.setenv("OCR_MAX_PAGES", "1")
    pages = [MagicMock(), MagicMock()]
    for page in pages:
        page.get_text.return_value = ""
    document = MagicMock()
    document.__iter__.return_value = pages
    mock_fitz_open.return_value = document
    mock_extract_page_text.return_value = "ocr text"

    with pytest.raises(ValueError, match="limited to 1 OCR pages"):
        parse_document_sections(b"pdf", "large-scan.pdf")

    assert mock_extract_page_text.call_count == 1
    document.close.assert_called_once()


def test_chunk_text() -> None:
    # Simulate a Persian text
    persian_text = "این یک متن تستی برای سیستم پردازش زبان طبیعی پارس رگ است. " * 50
    nodes = chunk_text(persian_text, metadata={"source": "test.txt"})

    assert len(nodes) > 0
    assert nodes[0].metadata["source"] == "test.txt"
    # Ensure splitting happened (50 sentences should be split into multiple chunks)
    assert len(nodes) > 1
    assert len(nodes[0].text) > 0


def test_real_docx_parsing() -> None:
    """End-to-End ingestion parser test using a real file from testData copied to data/."""
    file_path = os.path.join(
        os.path.dirname(__file__), "../../../data/نیازمندی‌های تست.docx"
    )

    if not os.path.exists(file_path):
        pytest.skip("Test file 'نیازمندی‌های تست.docx' not found in data/ directory.")

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    text = parse_document(file_bytes, "نیازمندی‌های تست.docx")
    assert len(text) > 0
    assert "تست" in text


@pytest.mark.parametrize(
    ("filename", "payload", "expected"),
    [
        ("notes.txt", "متن ساده".encode(), "متن ساده"),
        ("guide.md", "# راهنما\n\nجزئیات".encode(), "# راهنما"),
        (
            "data.json",
            json.dumps({"name": "پارس‌رگ"}, ensure_ascii=False).encode(),
            "پارس‌رگ",
        ),
        ("table.csv", b"name,value\nalpha,42", "alpha"),
        ("page.html", b"<h1>Title</h1><p>Body</p>", "Title"),
    ],
)
def test_textual_formats_are_parsed(
    filename: str, payload: bytes, expected: str
) -> None:
    """Common UTF-8 knowledge formats are accepted without lossy conversion."""
    sections = parse_document_sections(payload, filename)

    assert expected in sections[0].text
    assert sections[0].metadata == {"section": 1}


@patch("backend.infrastructure.parsers.document_parser.extract_image_text")
def test_standalone_image_uses_ocr(
    mock_extract: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A raster image is a first-class OCR document."""
    monkeypatch.setenv("OCR_ENABLED", "1")
    mock_extract.return_value = "متن روی تصویر"

    sections = parse_document_sections(b"image", "scan.png")

    assert sections == [ParsedSection("متن روی تصویر", {"page": 1})]


@patch("backend.infrastructure.parsers.document_parser.extract_image_text")
def test_docx_embedded_image_is_ocred_when_enabled(
    mock_extract: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pictures embedded in Word contribute OCR text at their paragraph location."""
    monkeypatch.setenv("OCR_ENABLED", "1")
    mock_extract.return_value = "نوشته داخل تصویر ورد"
    image = BytesIO()
    Image.new("RGB", (400, 200), "white").save(image, format="PNG")
    document = Document()
    document.add_picture(BytesIO(image.getvalue()))
    payload = BytesIO()
    document.save(payload)

    sections = parse_document_sections(payload.getvalue(), "image-only.docx")

    assert sections[0].text == "نوشته داخل تصویر ورد"
    assert sections[0].metadata == {"paragraph": 1}
    mock_extract.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.extract_image_text")
def test_pptx_picture_is_ocred_with_slide_metadata(
    mock_extract: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pictures embedded in PowerPoint keep their slide citation after OCR."""
    monkeypatch.setenv("OCR_ENABLED", "1")
    mock_extract.return_value = "نوشته داخل تصویر پاورپوینت"
    image = BytesIO()
    Image.new("RGB", (400, 200), "white").save(image, format="PNG")
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_picture(BytesIO(image.getvalue()), Inches(1), Inches(1))
    payload = BytesIO()
    presentation.save(payload)

    sections = parse_document_sections(payload.getvalue(), "image-only.pptx")

    assert sections[0].text == "نوشته داخل تصویر پاورپوینت"
    assert sections[0].metadata == {"slide": 1}
    mock_extract.assert_called_once()
