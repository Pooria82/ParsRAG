import io
from dataclasses import dataclass
from typing import Any

import fitz  # type: ignore  # PyMuPDF
from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from pptx import Presentation

from backend.core.exceptions import EmptyDocumentError
from backend.infrastructure.parsers.ocr import (
    OCRError,
    OCRPageLimitError,
    OCRSettings,
    extract_page_text,
)

__all__ = [
    "EmptyDocumentError",
    "ParsedSection",
    "parse_document",
    "parse_document_sections",
]


@dataclass(frozen=True)
class ParsedSection:
    """Text extracted from a traceable document location."""

    text: str
    metadata: dict[str, int]


def parse_document(file_bytes: bytes, filename: str) -> str:
    """Extracts text content from a PDF, DOCX, or PPTX file byte stream.

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
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        return _parse_pdf(file_bytes)
    elif lower_name.endswith(".docx"):
        return _parse_docx(file_bytes)
    elif lower_name.endswith(".pptx"):
        return _parse_pptx(file_bytes)
    else:
        raise ValueError(
            "Unsupported file format. Only PDF, DOCX, and PPTX are supported."
        )


def parse_document_sections(file_bytes: bytes, filename: str) -> list[ParsedSection]:
    """Extracts text with page, slide, paragraph, or section metadata."""
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        sections = _parse_pdf_sections(file_bytes)
    elif lower_name.endswith(".docx"):
        try:
            document = Document(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ValueError("Corrupted or invalid DOCX document.") from exc
        sections = []
        paragraph = 0
        for section_index, child in enumerate(
            document.element.body.iterchildren(), start=1
        ):
            if isinstance(child, CT_P):
                value = Paragraph(child, document).text.strip()
                if value:
                    paragraph += 1
                    sections.append(ParsedSection(value, {"paragraph": paragraph}))
            elif isinstance(child, CT_Tbl):
                value = _format_docx_table(Table(child, document)).strip()
                if value:
                    sections.append(ParsedSection(value, {"section": section_index}))
    elif lower_name.endswith(".pptx"):
        try:
            presentation = Presentation(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ValueError("Corrupted or invalid PPTX document.") from exc
        sections = []
        for slide_index, slide in enumerate(presentation.slides, start=1):
            parts: list[str] = []
            for shape in slide.shapes:
                if getattr(shape, "has_table", False):
                    parts.append(_format_pptx_table(shape.table))
                elif hasattr(shape, "text") and shape.text and shape.text.strip():
                    parts.append(shape.text.strip())
            if text := "\n\n".join(part for part in parts if part).strip():
                sections.append(ParsedSection(text, {"slide": slide_index}))
    else:
        raise ValueError(
            "Unsupported file format. Only PDF, DOCX, and PPTX are supported."
        )
    if not sections:
        if lower_name.endswith(".pdf"):
            raise EmptyDocumentError("Scanned PDFs require OCR, but OCR is disabled.")
        raise EmptyDocumentError("The document contains no text.")
    return sections


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
            for h, val in zip(headers, row):
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


def _parse_pdf(file_bytes: bytes) -> str:
    """Extracts native and OCR text from PDF bytes."""
    sections = _parse_pdf_sections(file_bytes)
    if not sections:
        raise EmptyDocumentError("Scanned PDFs require OCR, but OCR is disabled.")
    return "\n\n".join(section.text for section in sections)


def _parse_pdf_sections(file_bytes: bytes) -> list[ParsedSection]:
    """Extracts ordered PDF pages, using OCR only for scanned pages."""
    try:
        document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError("Corrupted or invalid PDF document.") from exc

    settings = OCRSettings.from_environment()
    sections: list[ParsedSection] = []
    scanned_pages = 0
    try:
        for page_number, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if not text:
                scanned_pages += 1
                if not settings.enabled:
                    continue
                if scanned_pages > settings.max_pages:
                    raise OCRPageLimitError(
                        f"Scanned PDFs are limited to {settings.max_pages} OCR pages."
                    )
                try:
                    text = extract_page_text(page, settings)
                except OCRError as exc:
                    raise ValueError(
                        f"Scanned PDFs could not be processed: {exc}"
                    ) from exc
            if text:
                sections.append(
                    ParsedSection(text=text, metadata={"page": page_number})
                )
    finally:
        document.close()
    return sections


def _parse_docx(file_bytes: bytes) -> str:
    """Extracts text and tables sequentially from DOCX bytes."""
    try:
        doc = Document(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError("Corrupted or invalid DOCX document.") from e

    parts: list[str] = []
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            p = Paragraph(child, doc)
            if p.text and p.text.strip():
                parts.append(p.text.strip())
        elif isinstance(child, CT_Tbl):
            t = Table(child, doc)
            tbl_str = _format_docx_table(t)
            if tbl_str and tbl_str.strip():
                parts.append(tbl_str.strip())

    text = "\n\n".join(parts)
    if not text.strip():
        raise EmptyDocumentError("The DOCX document contains no text.")

    return text.strip()


def _parse_pptx(file_bytes: bytes) -> str:
    """Extracts text and tables from PPTX bytes."""
    try:
        prs = Presentation(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError("Corrupted or invalid PPTX document.") from e

    parts: list[str] = []
    for slide_idx, slide in enumerate(prs.slides, start=1):
        parts.append(f"--- اسلاید {slide_idx} ---")
        for shape in slide.shapes:
            if getattr(shape, "has_table", False):
                tbl_str = _format_pptx_table(shape.table)
                if tbl_str:
                    parts.append(tbl_str)
            elif hasattr(shape, "text") and shape.text and shape.text.strip():
                parts.append(shape.text.strip())

    text = "\n\n".join(parts)
    if not text.strip():
        raise EmptyDocumentError("The PPTX document contains no text.")

    return text.strip()
