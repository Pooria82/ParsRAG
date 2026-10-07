import json
import os
from io import BytesIO
from unittest.mock import MagicMock, patch

import pymupdf
import pytest
from docx import Document
from PIL import Image
from pptx import Presentation
from pptx.util import Inches

from backend.core.domain.documents import ParsedSection
from backend.core.domain.exceptions import DocumentError, EmptyDocumentError
from backend.infrastructure.parsers.chunker import bridge_adjacent_pages, chunk_text
from backend.infrastructure.parsers.document_parser import (
    parse_document,
    parse_document_file,
    parse_document_sections,
)


@patch("backend.infrastructure.parsers.document_parser.pymupdf.open")
def test_parse_empty_pdf(mock_fitz_open: MagicMock) -> None:
    # Mock a PDF document with one page but no text
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = ""

    # Doc behaves like an iterator of pages
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz_open.return_value = mock_doc

    with pytest.raises(EmptyDocumentError, match="require OCR") as raised:
        parse_document(b"fake pdf bytes", "fake.pdf")
    assert raised.value.code == "ocr_disabled"

    mock_doc.close.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.pymupdf.open")
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
@patch("backend.infrastructure.parsers.document_parser.pymupdf.open")
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


@patch("backend.infrastructure.parsers.document_parser.extract_page_text")
@patch("backend.infrastructure.parsers.document_parser.pymupdf.open")
def test_garbled_text_layers_are_replaced_by_ocr(
    mock_fitz_open: MagicMock,
    mock_extract_page_text: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pages whose fonts lack Unicode maps are read by OCR, not appended to it."""
    monkeypatch.setenv("OCR_ENABLED", "true")
    garbled = MagicMock()
    garbled.get_text.return_value = "ÊÌåÇ ÈÑÇí ÊÓÊ ÇÓÊ " * 5
    document = MagicMock()
    document.__iter__.return_value = [garbled]
    mock_fitz_open.return_value = document
    mock_extract_page_text.return_value = "متن بازخوانی شده"

    sections = parse_document_sections(b"pdf", "broken-font.pdf")

    assert [section.text for section in sections] == ["متن بازخوانی شده"]
    document.close.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.extract_page_text")
@patch("backend.infrastructure.parsers.document_parser.pymupdf.open")
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
@patch("backend.infrastructure.parsers.document_parser.pymupdf.open")
def test_sparse_pdf_text_layer_does_not_hide_image_evidence(
    mock_open: MagicMock,
    mock_extract: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A short searchable title must not suppress OCR of the main page image."""
    monkeypatch.setenv("OCR_ENABLED", "1")
    page = MagicMock()
    page.get_text.return_value = "Invoice 42"
    page.get_images.return_value = [(1,)]
    mock_open.return_value.__iter__.return_value = [page]
    mock_extract.return_value = "Total due: 425 euros"

    sections = parse_document_sections(b"pdf", "invoice.pdf")

    assert sections == [
        ParsedSection("Invoice 42\n\nTotal due: 425 euros", {"page": 1})
    ]
    mock_extract.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.extract_page_text")
@patch("backend.infrastructure.parsers.document_parser.pymupdf.open")
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

    parsed = parse_document_file(b"pdf", "large-scan.pdf")

    assert [section.metadata for section in parsed.sections] == [{"page": 1}]
    assert parsed.notices == ("ocr_page_limit",)
    assert mock_extract_page_text.call_count == 1
    document.close.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.pymupdf.open")
def test_password_protected_pdf_is_reported_as_encrypted(
    mock_fitz_open: MagicMock,
) -> None:
    document = MagicMock()
    document.needs_pass = True
    mock_fitz_open.return_value = document

    with pytest.raises(DocumentError) as raised:
        parse_document_file(b"%PDF-1.7", "secret.pdf")

    assert raised.value.code == "encrypted_document"
    document.close.assert_called_once()


@patch("backend.infrastructure.parsers.document_parser.extract_image_text")
def test_office_images_past_the_limit_are_skipped_not_fatal(
    mock_extract: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Text around the 31st image is still indexed; a notice says what was skipped."""
    from backend.infrastructure.parsers.document_parser import _extract_embedded_image
    from backend.infrastructure.parsers.ocr import OCRError, OCRSettings

    monkeypatch.setenv("OCR_MAX_IMAGES", "1")
    settings = OCRSettings.from_environment()
    notices: list[str] = []
    mock_extract.return_value = "chart caption"

    first = _extract_embedded_image(b"img", settings, 0, notices)
    second = _extract_embedded_image(b"img", settings, 1, notices)
    mock_extract.side_effect = OCRError("unreadable")
    third = _extract_embedded_image(
        b"img", OCRSettings(True, "fas", 200, 30, 30), 0, notices
    )

    assert first == ("chart caption", 1)
    assert second == ("", 2)
    assert third == ("", 1)
    assert notices == ["ocr_image_limit", "ocr_partial"]


def test_missing_tesseract_is_reported_instead_of_skipped() -> None:
    """OCR that cannot run at all is a setup problem, not a partial result."""
    from backend.infrastructure.parsers.document_parser import _extract_embedded_image
    from backend.infrastructure.parsers.ocr import OCRSettings, OCRUnavailableError

    with (
        patch(
            "backend.infrastructure.parsers.document_parser.extract_image_text",
            side_effect=OCRUnavailableError("missing"),
        ),
        pytest.raises(DocumentError) as raised,
    ):
        _extract_embedded_image(b"img", OCRSettings(True, "fas", 200, 30, 30), 0, [])
    assert raised.value.code == "ocr_unavailable"


def test_non_utf8_text_has_an_encoding_code() -> None:
    with pytest.raises(DocumentError) as raised:
        parse_document_file("سلام".encode("utf-16"), "notes.txt")
    assert raised.value.code in {"text_encoding", "unsupported_file"}


def test_chunk_text() -> None:
    # Simulate a Persian text
    persian_text = "این یک متن تستی برای سیستم پردازش زبان طبیعی پارس رگ است. " * 50
    nodes = chunk_text(persian_text, metadata={"source": "test.txt"})

    assert len(nodes) > 0
    assert nodes[0].metadata["source"] == "test.txt"
    # Ensure splitting happened (50 sentences should be split into multiple chunks)
    assert len(nodes) > 1
    assert len(nodes[0].text) > 0


def test_page_bridge_keeps_both_sides_bounded_and_traceable() -> None:
    """A sentence split by a page turn remains one searchable evidence chunk."""
    previous = " ".join(["prefix"] * 150 + ["invoice", "total", "is"])
    current = " ".join(["425", "euros"] + ["suffix"] * 150)

    bridge = bridge_adjacent_pages(
        previous, current, filename="scan.pdf", previous_page=3, current_page=4
    )

    assert bridge is not None
    assert "invoice total is\n[page 4] 425 euros" in bridge.text
    assert bridge.metadata == {
        "filename": "scan.pdf",
        "page": 3,
        "page_end": 4,
        "kind": "page_bridge",
    }
    assert len(bridge.text.split()) <= 184
    assert (
        bridge_adjacent_pages(
            previous, current, filename="scan.pdf", previous_page=3, current_page=5
        )
        is None
    )


def test_real_two_page_pdf_preserves_one_split_fact() -> None:
    """A real PDF page turn keeps both halves available to one retrieval chunk."""
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "The invoice total is")
    document.new_page().insert_text((72, 72), "425 euros due today")
    payload = document.tobytes()
    document.close()

    sections = parse_document_sections(payload, "invoice.pdf")
    bridge = bridge_adjacent_pages(
        sections[0].text,
        sections[1].text,
        filename="invoice.pdf",
        previous_page=sections[0].metadata["page"],
        current_page=sections[1].metadata["page"],
    )

    assert bridge is not None
    assert "invoice total is\n[page 2] 425 euros" in bridge.text


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
