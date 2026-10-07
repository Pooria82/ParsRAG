import io
import json
import re
from html.parser import HTMLParser
from typing import Any, Protocol

import pymupdf
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from backend.core.domain.documents import ParsedDocument, ParsedSection
from backend.core.domain.exceptions import DocumentError, EmptyDocumentError
from backend.core.domain.upload_policy import IMAGE_EXTENSIONS, TEXT_EXTENSIONS
from backend.infrastructure.parsers.ocr import (
    OCRError,
    OCRSettings,
    OCRTimeoutError,
    OCRUnavailableError,
    RasterizablePage,
    extract_image_text,
    extract_page_text,
)
from backend.infrastructure.parsers.pdf_text import (
    logical_page_text,
    text_layer_is_garbled,
)

# Notice codes returned with a document that was indexed only in part.
NOTICE_OCR_PAGE_LIMIT = "ocr_page_limit"
NOTICE_OCR_IMAGE_LIMIT = "ocr_image_limit"
NOTICE_OCR_PARTIAL = "ocr_partial"
NOTICE_OCR_UNAVAILABLE = "ocr_unavailable"

__all__ = [
    "LocalDocumentParser",
    "parse_document",
    "parse_document_sections",
]


class _PDFPage(RasterizablePage, Protocol):
    """Parser-visible PDF page methods used to decide whether OCR is needed."""

    def get_text(self, option: str) -> str:
        """Extract the searchable text layer."""

    def get_images(self, *, full: bool) -> list[object]:
        """List raster images embedded on the page."""


class _VisibleTextExtractor(HTMLParser):
    """Collect visible text from simple HTML without executing or retaining markup."""

    def __init__(self) -> None:
        """Initialize an empty text collector."""
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Ignore executable/style blocks and separate structural elements."""
        del attrs
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        elif tag in {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Restore collection after ignored blocks and preserve block boundaries."""
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        """Collect text outside ignored elements."""
        if not self._ignored_depth:
            self.parts.append(data)


def parse_document(file_bytes: bytes, filename: str) -> str:
    """Extract text content from one supported knowledge-file byte stream.

    Preserves chronological document structure and converts tables into
    well-formatted Markdown with row-level header associations.

    Args:
        file_bytes (bytes): The raw bytes of the file.
        filename (str): The name of the file to determine its type.

    Returns:
        str: The extracted text from the document.

    Raises:
        EmptyDocumentError: If the document contains no text.
        ValueError: If the file format is unsupported.
    """
    sections = parse_document_sections(file_bytes, filename)
    if filename.lower().endswith(".pptx"):
        return "\n\n".join(
            f"--- اسلاید {section.metadata['slide']} ---\n\n{section.text}"
            for section in sections
        )
    return "\n\n".join(section.text for section in sections)


def parse_document_sections(file_bytes: bytes, filename: str) -> list[ParsedSection]:
    """Extracts text with page, slide, paragraph, or section metadata."""
    return parse_document_file(file_bytes, filename).sections


def parse_document_file(file_bytes: bytes, filename: str) -> ParsedDocument:
    """Extract sections and notices about parts skipped by OCR limits.

    Raises:
        DocumentError: The file is unsupported, corrupted, or encrypted.
        EmptyDocumentError: No text could be extracted.
    """
    lower_name = filename.lower()
    notices: list[str] = []
    settings = OCRSettings.from_environment()
    if lower_name.endswith(".pdf"):
        sections = _parse_pdf_sections(file_bytes, notices)
    elif lower_name.endswith(".docx"):
        sections = _parse_docx_sections(file_bytes, notices)
    elif lower_name.endswith(".pptx"):
        sections = _parse_pptx_sections(file_bytes, notices)
    elif lower_name.endswith(IMAGE_EXTENSIONS):
        sections = _parse_image_sections(file_bytes)
    elif lower_name.endswith(TEXT_EXTENSIONS):
        sections = _parse_text_sections(file_bytes, lower_name)
    else:
        raise DocumentError("Unsupported file format.", "unsupported_file")
    if not sections:
        if NOTICE_OCR_UNAVAILABLE in notices:
            raise DocumentError(
                "The document needs OCR, but Tesseract OCR is not installed.",
                "ocr_unavailable",
            )
        needs_ocr = lower_name.endswith((".pdf", *IMAGE_EXTENSIONS))
        if needs_ocr and not settings.enabled:
            raise EmptyDocumentError(
                "Scanned documents require OCR, but OCR is disabled.", "ocr_disabled"
            )
        if needs_ocr:
            raise EmptyDocumentError(
                "OCR found no readable text in the document.", "no_readable_text"
            )
        raise EmptyDocumentError("The document contains no text.")
    return ParsedDocument(sections, tuple(dict.fromkeys(notices)))


class LocalDocumentParser:
    """``DocumentParser`` adapter backed by PyMuPDF, python-docx/pptx, and OCR."""

    def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """Extract traceable sections with the format-specific local parser."""
        return parse_document_file(file_bytes, filename)


def _parse_docx_sections(file_bytes: bytes, notices: list[str]) -> list[ParsedSection]:
    """Extract traceable paragraphs and tables from DOCX bytes."""
    try:
        document = Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise DocumentError(
            "Corrupted or invalid DOCX document.", "corrupt_file"
        ) from exc
    settings = OCRSettings.from_environment()
    builder = _DocxSectionBuilder()
    paragraph = 0
    ocr_images = 0
    for section_index, child in enumerate(
        document.element.body.iterchildren(), start=1
    ):
        if isinstance(child, CT_P):
            paragraph_object = Paragraph(child, document)
            images: list[str] = []
            if settings.enabled:
                for image in _docx_paragraph_images(paragraph_object, document):
                    recognized, ocr_images = _extract_embedded_image(
                        image, settings, ocr_images, notices
                    )
                    images.append(recognized)
            if builder.add(paragraph_object, images, paragraph + 1):
                paragraph += 1
        elif isinstance(child, CT_Tbl):
            value = _format_docx_table(Table(child, document)).strip()
            if value:
                builder.table(value, section_index)
    return builder.finish()


# Word paragraphs are often a single line; one chunk per paragraph produced
# 9-18 word chunks that lost their context. Paragraphs under the same heading
# are grouped up to roughly one chunk, and every group carries its heading path.
_MAX_SECTION_WORDS = 180
_MAX_HEADING_WORDS = 25
_HEADING_STYLE = re.compile(r"^(?:heading|title|عنوان)\s*(\d*)$", re.IGNORECASE)


def _docx_heading_level(paragraph: Paragraph) -> int | None:
    """Return 0 for a title, N for "Heading N", or None for body text."""
    style = paragraph.style
    while style is not None:
        match = _HEADING_STYLE.match((style.name or "").strip())
        if match:
            return int(match.group(1)) if match.group(1) else 0
        style = style.base_style
    outline = paragraph._p.xpath("./w:pPr/w:outlineLvl/@w:val")
    return int(outline[0]) + 1 if outline else None


class _DocxSectionBuilder:
    """Group body paragraphs under their headings into chunk-sized sections."""

    def __init__(self) -> None:
        self.sections: list[ParsedSection] = []
        self.headings: dict[int, str] = {}
        self.parts: list[str] = []
        self.words = 0
        self.first = 0
        self.last = 0

    def _path(self) -> str:
        return " › ".join(self.headings[level] for level in sorted(self.headings))

    def _with_path(self, body: str) -> str:
        path = self._path()
        return f"{path}\n{body}" if path else body

    def flush(self) -> None:
        if not self.parts:
            return
        metadata = {"paragraph": self.first}
        if self.last > self.first:
            metadata["paragraph_end"] = self.last
        self.sections.append(
            ParsedSection(self._with_path("\n".join(self.parts)), metadata)
        )
        self.parts, self.words = [], 0

    def heading(self, level: int, text: str) -> None:
        self.flush()
        self.headings = {
            depth: title for depth, title in self.headings.items() if depth < level
        }
        self.headings[level] = text

    def paragraph(self, text: str, number: int) -> None:
        words = len(text.split())
        if self.parts and self.words + words > _MAX_SECTION_WORDS:
            self.flush()
        if not self.parts:
            self.first = number
        self.parts.append(text)
        self.words += words
        self.last = number

    def add(self, paragraph: Paragraph, images: list[str], number: int) -> bool:
        """Add one Word paragraph and its OCR'd images; return whether it had text."""
        text = paragraph.text.strip()
        recognized = "\n\n".join(image for image in images if image).strip()
        if not text and not recognized:
            return False
        level = _docx_heading_level(paragraph) if text else None
        if level is not None and len(text.split()) <= _MAX_HEADING_WORDS:
            self.heading(level, text)
            if recognized:
                self.paragraph(recognized, number)
        else:
            body = "\n\n".join(part for part in (text, recognized) if part)
            self.paragraph(body, number)
        return True

    def table(self, text: str, position: int) -> None:
        self.flush()
        self.sections.append(
            ParsedSection(self._with_path(text), {"section": position})
        )

    def finish(self) -> list[ParsedSection]:
        self.flush()
        if not self.sections and self.headings:
            # A document of headings only still has searchable text.
            self.sections.append(ParsedSection(self._path(), {"paragraph": 1}))
        return self.sections


def _parse_pptx_sections(file_bytes: bytes, notices: list[str]) -> list[ParsedSection]:
    """Extract traceable slide content and tables from PPTX bytes."""
    try:
        presentation = Presentation(io.BytesIO(file_bytes))
    except Exception as exc:
        raise DocumentError(
            "Corrupted or invalid PPTX document.", "corrupt_file"
        ) from exc
    settings = OCRSettings.from_environment()
    sections: list[ParsedSection] = []
    ocr_images = 0
    for slide_index, slide in enumerate(presentation.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            if getattr(shape, "has_table", False):
                parts.append(_format_pptx_table(shape.table))
            elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE and settings.enabled:
                text, ocr_images = _extract_embedded_image(
                    shape.image.blob, settings, ocr_images, notices
                )
                if text:
                    parts.append(text)
            elif hasattr(shape, "text") and shape.text and shape.text.strip():
                parts.append(shape.text.strip())
        if text := "\n\n".join(part for part in parts if part).strip():
            sections.append(ParsedSection(text, {"slide": slide_index}))
    return sections


def _docx_paragraph_images(paragraph: Paragraph, document: Any) -> list[bytes]:
    """Return image blobs referenced by one Word paragraph in document order."""
    images: list[bytes] = []
    relationship_ids = paragraph._p.xpath(".//a:blip/@r:embed")
    for relationship_id in relationship_ids:
        related_part = document.part.related_parts.get(relationship_id)
        blob = getattr(related_part, "blob", None)
        if isinstance(blob, bytes):
            images.append(blob)
    return images


def _ocr_unavailable(exc: OCRUnavailableError) -> DocumentError:
    """OCR cannot run at all for a file that is only an image."""
    return DocumentError(f"OCR is unavailable: {exc}", "ocr_unavailable")


def _extract_embedded_image(
    image: bytes, settings: OCRSettings, processed: int, notices: list[str]
) -> tuple[str, int]:
    """OCR one Office image within the image budget; skip it when over budget.

    Text of the rest of the document is still indexed: images past
    ``OCR_MAX_IMAGES`` or images OCR cannot read only add a notice.
    """
    next_count = processed + 1
    if next_count > settings.max_images:
        notices.append(NOTICE_OCR_IMAGE_LIMIT)
        return "", next_count
    try:
        return extract_image_text(image, settings), next_count
    except OCRUnavailableError:
        notices.append(NOTICE_OCR_UNAVAILABLE)
        return "", next_count
    except (OCRError, ValueError):
        notices.append(NOTICE_OCR_PARTIAL)
        return "", next_count


def _parse_image_sections(file_bytes: bytes) -> list[ParsedSection]:
    """Extract OCR text from a standalone raster image."""
    settings = OCRSettings.from_environment()
    if not settings.enabled:
        return []
    try:
        text = extract_image_text(file_bytes, settings)
    except OCRUnavailableError as exc:
        raise _ocr_unavailable(exc) from exc
    except OCRTimeoutError as exc:
        raise DocumentError(f"OCR timed out: {exc}", "ocr_timeout") from exc
    except OCRError as exc:
        raise DocumentError(
            f"The image could not be processed: {exc}", "ocr_failed"
        ) from exc
    except ValueError as exc:
        raise DocumentError(str(exc), "corrupt_file") from exc
    return [ParsedSection(text, {"page": 1})] if text else []


_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
# Below this share of Arabic-script letters, a Windows-1256 reading is not
# Persian/Arabic text and Windows-1252 (Western) is used instead.
_MIN_ARABIC_LETTER_SHARE = 0.3


def _arabic_letter_share(text: str) -> float:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return 0.0
    arabic = sum("؀" <= char <= "ۿ" for char in letters)
    return arabic / len(letters)


def _decode_text(file_bytes: bytes) -> str:
    """Decode text files: UTF-8, UTF-16 with BOM, or legacy Windows code pages.

    Persian text saved by older Windows editors (Notepad before 2019, Excel
    CSV exports) uses Windows-1256; Western files use Windows-1252. Binary
    payloads are rejected.
    """
    if file_bytes.startswith(_UTF16_BOMS):
        try:
            return file_bytes.decode("utf-16")
        except UnicodeDecodeError as exc:
            raise DocumentError(
                "The UTF-16 text file is malformed.", "text_encoding"
            ) from exc
    if b"\x00" in file_bytes:
        raise DocumentError("The text file contains binary data.", "unsupported_file")
    try:
        return file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    persian = file_bytes.decode("cp1256", errors="replace")
    if _arabic_letter_share(persian) >= _MIN_ARABIC_LETTER_SHARE:
        return persian.replace("�", "")
    try:
        return file_bytes.decode("cp1252")
    except UnicodeDecodeError as exc:
        raise DocumentError(
            "The text encoding was not recognized; save the file as UTF-8.",
            "text_encoding",
        ) from exc


def _parse_text_sections(file_bytes: bytes, filename: str) -> list[ParsedSection]:
    """Parse structured and plain UTF-8 knowledge formats."""
    text = _decode_text(file_bytes)
    if filename.endswith(".json"):
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DocumentError(
                "The JSON document is invalid.", "corrupt_file"
            ) from exc
        text = json.dumps(value, ensure_ascii=False, indent=2)
    elif filename.endswith((".html", ".htm", ".xml")):
        parser = _VisibleTextExtractor()
        parser.feed(text)
        text = "\n".join(
            line.strip() for line in "".join(parser.parts).splitlines() if line.strip()
        )
    text = text.strip()
    return [ParsedSection(text, {"section": 1})] if text else []


def _clean_cell_text(text: str) -> str:
    """Cleans cell text by normalizing whitespace and escaping markdown pipes."""
    clean = " ".join(text.split())
    return clean.replace("|", "\\|")


def _format_table_grid(grid_rows: list[list[str]]) -> str:
    """Converts a grid of strings into Markdown table with structured row records.

    Args:
        grid_rows (list[list[str]]): 2D list of cleaned cell strings.

    Returns:
        str: Formatted Markdown table and structured records.
    """
    if not grid_rows:
        return ""

    num_rows = len(grid_rows)
    max_cols = max(len(r) for r in grid_rows)

    # 1x1 callout or code box
    if num_rows == 1 and max_cols == 1:
        content = grid_rows[0][0]
        return f"> [کادر محتوا]:\n> {content}"

    # Pad any short rows to max_cols
    for row in grid_rows:
        while len(row) < max_cols:
            row.append("-")

    # Header resolution
    headers = [
        col if col else f"ستون_{idx + 1}" for idx, col in enumerate(grid_rows[0])
    ]

    # Build Markdown table
    md_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join([":---"] * max_cols) + " |",
    ]
    for row in grid_rows[1:]:
        row_cells = [c if c else "-" for c in row]
        md_lines.append("| " + " | ".join(row_cells) + " |")

    table_md = "\n".join(md_lines)

    # Build Structured Row Records for tables with >= 2 columns and >= 2 rows
    # This prevents orphaned cell values when chunks split across table rows
    if max_cols >= 2 and num_rows >= 2:
        record_lines = ["\n[سوابق ردیف‌های جدول]:"]
        for r_idx, row in enumerate(grid_rows[1:], start=1):
            items = []
            for h, val in zip(headers, row, strict=False):
                cell_val = val if val else "-"
                items.append(f"[{h}]: {cell_val}")
            record_lines.append(f"- سطر {r_idx}: " + " | ".join(items))
        table_md += "\n" + "\n".join(record_lines)

    return table_md


def _format_docx_table(table: Table) -> str:
    """Formats a DOCX table into Markdown and row records, handling merged cells."""
    if not table.rows:
        return ""

    grid_rows: list[list[str]] = []
    for row in table.rows:
        # Deduplicate horizontally merged cells
        unique_cells: list[_Cell] = []
        for cell in row.cells:
            if not unique_cells or cell._tc != unique_cells[-1]._tc:
                unique_cells.append(cell)
        row_vals = [_clean_cell_text(cell.text) for cell in unique_cells]
        if any(row_vals):
            grid_rows.append(row_vals)

    return _format_table_grid(grid_rows)


def _format_pptx_table(table: Any) -> str:
    """Formats a PPTX table shape into Markdown and row records."""
    grid_rows: list[list[str]] = []
    for row in table.rows:
        row_vals = [_clean_cell_text(cell.text) for cell in row.cells]
        if any(row_vals):
            grid_rows.append(row_vals)

    return _format_table_grid(grid_rows)


def _needs_pdf_ocr(page: _PDFPage, text: str, settings: OCRSettings) -> bool:
    """Detect scanned pages, broken text layers, and sparse image pages."""
    if not text:
        return True
    if settings.enabled and text_layer_is_garbled(text):
        return True
    if not settings.enabled or sum(char.isalnum() for char in text) >= 40:
        return False
    images = page.get_images(full=True)
    return isinstance(images, list) and bool(images)


def _pdf_page_text(
    page: _PDFPage,
    text: str,
    settings: OCRSettings,
    scanned_pages: int,
    notices: list[str],
) -> tuple[str, int]:
    """OCR one suspect page while retaining usable native text on OCR failure.

    Pages past ``OCR_MAX_PAGES`` and pages OCR cannot read keep their native
    text (often empty) and add a notice instead of rejecting the document.
    """
    if not _needs_pdf_ocr(page, text, settings):
        return text, scanned_pages
    scanned_pages += 1
    if not settings.enabled:
        return "" if text_layer_is_garbled(text) else text, scanned_pages
    if scanned_pages > settings.max_pages:
        notices.append(NOTICE_OCR_PAGE_LIMIT)
        return "" if text_layer_is_garbled(text) else text, scanned_pages
    try:
        recognized = extract_page_text(page, settings)
    except OCRUnavailableError:
        # The text pages are still useful; the notice names the setup problem.
        notices.append(NOTICE_OCR_UNAVAILABLE)
        return "" if text_layer_is_garbled(text) else text, scanned_pages
    except OCRError:
        notices.append(NOTICE_OCR_PARTIAL)
        return "" if text_layer_is_garbled(text) else text, scanned_pages
    if recognized and text_layer_is_garbled(text):
        return recognized, scanned_pages
    if recognized and text and text not in recognized:
        return f"{text}\n\n{recognized}", scanned_pages
    return recognized or text, scanned_pages


def _parse_pdf_sections(file_bytes: bytes, notices: list[str]) -> list[ParsedSection]:
    """Extract ordered PDF pages and OCR image pages with sparse text layers."""
    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise DocumentError(
            "Corrupted or invalid PDF document.", "corrupt_file"
        ) from exc
    if getattr(document, "needs_pass", False) is True:
        document.close()
        raise DocumentError("The PDF is password-protected.", "encrypted_document")

    settings = OCRSettings.from_environment()
    sections: list[ParsedSection] = []
    scanned_pages = 0
    try:
        for page_number, page in enumerate(document, start=1):
            text = logical_page_text(page)
            text, scanned_pages = _pdf_page_text(
                page, text, settings, scanned_pages, notices
            )
            if text:
                sections.append(
                    ParsedSection(text=text, metadata={"page": page_number})
                )
    finally:
        document.close()
    return sections
