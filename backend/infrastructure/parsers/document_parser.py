import csv
import io
import json
import os
import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from html.parser import HTMLParser
from typing import Any, Protocol

import pymupdf
from docx import Document
from docx.oxml.ns import qn
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from PIL import Image, UnidentifiedImageError
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER

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
    recognize_page_png,
    render_page_png,
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


# Elements that start a new line of visible text.
_HTML_BLOCKS = frozenset(
    {
        "p",
        "div",
        "li",
        "tr",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "table",
        "section",
        "article",
        "header",
        "footer",
        "ul",
        "ol",
        "blockquote",
        "pre",
        "dd",
        "dt",
        "figcaption",
        "caption",
        "main",
        "aside",
        "nav",
    }
)


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
        elif tag in _HTML_BLOCKS or tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Restore collection after ignored blocks and preserve block boundaries."""
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in _HTML_BLOCKS:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            # Without a separator, <td>Name</td><td>Ali</td> read "NameAli".
            self.parts.append(" | ")

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
    blobs: dict[int, bytes] = {}
    settings = OCRSettings.from_environment()
    if lower_name.endswith(".pdf"):
        sections = _parse_pdf_sections(file_bytes, notices)
    elif lower_name.endswith(".docx"):
        sections = _parse_docx_sections(file_bytes, notices, blobs)
    elif lower_name.endswith(".pptx"):
        sections = _parse_pptx_sections(file_bytes, notices, blobs)
    elif lower_name.endswith(IMAGE_EXTENSIONS):
        sections = _parse_image_sections(file_bytes, blobs)
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
    return ParsedDocument(
        sections, tuple(dict.fromkeys(notices)), _section_previews(sections, blobs)
    )


# Longest side of an image preview shown next to its source excerpt.
_PREVIEW_MAX_SIDE = 1280
_PREVIEW_QUALITY = 80


def source_image_previews_enabled() -> bool:
    """Whether cited images are kept as previews (``SOURCE_IMAGE_PREVIEWS``)."""
    return os.getenv("SOURCE_IMAGE_PREVIEWS", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def image_preview(blob: bytes) -> bytes | None:
    """A WebP copy of an image, at most 1280 px on its longest side.

    Returns None for data Pillow cannot read, so a broken picture never
    blocks indexing.
    """
    try:
        with Image.open(io.BytesIO(blob)) as image:
            image.load()
            mode = "RGBA" if image.mode in {"RGBA", "LA", "P"} else "RGB"
            picture = image.convert(mode)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return None
    picture.thumbnail((_PREVIEW_MAX_SIDE, _PREVIEW_MAX_SIDE))
    output = io.BytesIO()
    picture.save(output, format="WEBP", quality=_PREVIEW_QUALITY, method=4)
    return output.getvalue()


def _section_previews(
    sections: list[ParsedSection], blobs: dict[int, bytes]
) -> dict[int, bytes]:
    """Previews of the images that became searchable sections."""
    if not blobs or not source_image_previews_enabled():
        return {}
    numbers = {
        number
        for section in sections
        if isinstance(number := section.metadata.get("image"), int)
    }
    previews: dict[int, bytes] = {}
    for number in sorted(numbers & blobs.keys()):
        preview = image_preview(blobs[number])
        if preview is not None:
            previews[number] = preview
    return previews


class LocalDocumentParser:
    """``DocumentParser`` adapter backed by PyMuPDF, python-docx/pptx, and OCR."""

    def parse(self, file_bytes: bytes, filename: str) -> ParsedDocument:
        """Extract traceable sections with the format-specific local parser."""
        return parse_document_file(file_bytes, filename)


def _parse_docx_sections(
    file_bytes: bytes, notices: list[str], blobs: dict[int, bytes] | None = None
) -> list[ParsedSection]:
    """Extract traceable paragraphs and tables from DOCX bytes.

    Images are read first and recognized several at a time; ``blobs`` receives
    each image by its number in the document.
    """
    try:
        document = Document(io.BytesIO(file_bytes))
    except Exception as exc:
        raise DocumentError(
            "Corrupted or invalid DOCX document.", "corrupt_file"
        ) from exc
    children = list(_body_blocks(document.element.body))
    readings = _docx_image_readings(children, document, notices, blobs)
    builder = _DocxSectionBuilder()
    paragraph = 0
    image_number = 0
    table_number = 0
    for index, child in enumerate(children):
        if isinstance(child, CT_P):
            paragraph_object = Paragraph(child, document)
            images: list[tuple[int, str]] = []
            for recognized in readings.get(index, []):
                image_number += 1
                images.append((image_number, recognized))
            if builder.add(paragraph_object, images, paragraph + 1):
                paragraph += 1
        elif isinstance(child, CT_Tbl):
            table_number = _add_docx_table(
                builder, Table(child, document), table_number, max(1, paragraph)
            )
    return builder.finish()


_SDT = qn("w:sdt")
_SDT_CONTENT = qn("w:sdtContent")
_DOC_PART_GALLERY = f"{qn('w:sdtPr')}/{qn('w:docPartObj')}/{qn('w:docPartGallery')}"


def _body_blocks(container: Any) -> Iterator[Any]:
    """Paragraphs and tables in reading order, including those in content controls.

    Templates and forms wrap their body in ``w:sdt`` blocks; reading only the
    top-level paragraphs and tables indexed nothing for them. A generated table
    of contents is also a ``w:sdt``; its heading-and-page-number lines would
    match questions without answering them, so it is skipped.
    """
    for child in container.iterchildren():
        if child.tag != _SDT:
            yield child
        elif not _is_table_of_contents(child):
            for content in child.iterchildren(_SDT_CONTENT):
                yield from _body_blocks(content)


def _is_table_of_contents(control: Any) -> bool:
    gallery = control.find(_DOC_PART_GALLERY)
    value = gallery.get(qn("w:val"), "") if gallery is not None else ""
    return str(value).lower().startswith("table of contents")


def _docx_image_readings(
    children: list[Any],
    document: Any,
    notices: list[str],
    blobs: dict[int, bytes] | None,
) -> dict[int, list[str]]:
    """OCR text of every Word image, grouped by the body element that holds it."""
    settings = OCRSettings.from_environment().with_deadline()
    owners: list[int] = []
    pictures: list[bytes] = []
    if settings.enabled:
        for index, child in enumerate(children):
            if isinstance(child, CT_P):
                paragraph = Paragraph(child, document)
                for image in _docx_paragraph_images(paragraph, document):
                    owners.append(index)
                    pictures.append(image)
    readings: dict[int, list[str]] = {}
    recognized = recognize_images(pictures, settings, notices)
    for owner, text in zip(owners, recognized, strict=True):
        readings.setdefault(owner, []).append(text)
    if blobs is not None:
        blobs.update(enumerate(pictures, start=1))
    return readings


# Word paragraphs are often a single line; one chunk per paragraph produced
# 9-18 word chunks that lost their context. Paragraphs under the same heading
# are grouped up to roughly one chunk, and every group carries its heading path.
_MAX_SECTION_WORDS = 180
_MAX_HEADING_WORDS = 25
_HEADING_STYLE = re.compile(r"^(?:heading|title|عنوان)\s*(\d*)$", re.IGNORECASE)
# Figure captions ("شکل ۳-۲: ...", "Figure 4. ...") sit just above or below their image.
_CAPTION = re.compile(
    r"^\s*(?:شکل|تصویر|نمودار|figure|fig\.)\s*[\d۰-۹(]", re.IGNORECASE
)
_MAX_CAPTION_WORDS = 40


def image_label(number: int) -> str:
    """The marker that starts an image's OCR text, so answers can cite the image."""
    return f"[تصویر {number}]"


_MAX_IMAGE_CONTEXT_CHARS = 300


def _image_section_text(
    number: int, caption: str, recognized: str, context: str = ""
) -> str:
    """An image's own searchable text: label, caption, the text leading to it, OCR.

    Reports describe a screenshot in the sentence before it ("to create a
    prompt, open ..."); OCR alone is short and noisy, so without that context
    the right image was not retrieved, or a near-identical one was cited.
    """
    head = f"{image_label(number)} {caption}".strip()
    lead = _tail(context, _MAX_IMAGE_CONTEXT_CHARS)
    return "\n".join(part for part in (head, lead, recognized) if part)


def _tail(text: str, limit: int) -> str:
    """The end of ``text``, at most ``limit`` characters, cut at a word boundary."""
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[-limit:]
    return "…" + cut[cut.find(" ") + 1 :] if " " in cut else "…" + cut


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
    """Group body paragraphs under their headings into chunk-sized sections.

    Each embedded image with OCR text becomes its own section, labeled with
    its number in the document and its caption, so an answer can cite the
    image itself rather than the paragraphs around it. Paragraph numbers count
    paragraphs with text only, so they do not shift with OCR results.
    """

    def __init__(self) -> None:
        self.sections: list[ParsedSection] = []
        self.headings: dict[int, str] = {}
        self.parts: list[str] = []
        self.words = 0
        self.first = 0
        self.last = 0
        self.previous_text = ""
        # Images waiting for a caption in the paragraph that follows them.
        # (number, paragraph, caption, leading context, OCR text) per image.
        self.pending: list[tuple[int, int, str, str, str]] = []

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

    def add(
        self, paragraph: Paragraph, images: list[tuple[int, str]], number: int
    ) -> bool:
        """Add one Word paragraph and its OCR'd images; return whether it had text.

        ``number`` is the paragraph's number if it has text; an image in an
        otherwise empty paragraph is placed after the previous paragraph.
        """
        text = paragraph.text.strip()
        is_caption = bool(text) and _is_caption(text)
        self._release_images(text if is_caption else "")
        if text:
            level = _docx_heading_level(paragraph)
            if level is not None and len(text.split()) <= _MAX_HEADING_WORDS:
                self.heading(level, text)
            else:
                self.paragraph(text, number)
        anchor = number if text else max(1, number - 1)
        above = text if text else self.previous_text
        for image_number, recognized in images:
            if recognized.strip():
                caption, context = (above, "") if _is_caption(above) else ("", above)
                self.pending.append(
                    (image_number, anchor, caption, context, recognized.strip())
                )
        if text:
            self.previous_text = text
        return bool(text)

    def _release_images(self, caption_below: str) -> None:
        """Emit waiting image sections, using a caption found below them."""
        for image_number, anchor, caption, context, recognized in self.pending:
            metadata = {"paragraph": anchor, "image": image_number}
            body = _image_section_text(
                image_number, caption or caption_below, recognized, context
            )
            self.sections.append(ParsedSection(self._with_path(body), metadata))
        self.pending = []

    def table(self, text: str, number: int, after_paragraph: int) -> None:
        """Add one table, cited by its number and the paragraph it follows.

        A body-element index (the old ``section``) cannot be found in Word;
        "paragraph 120 · table 3" can.
        """
        self.flush()
        self._release_images("")
        caption = self.previous_text if _is_table_caption(self.previous_text) else ""
        head = f"[جدول {number}] {caption}".strip()
        self.sections.append(
            ParsedSection(
                self._with_path(f"{head}\n{text}"),
                {"paragraph": after_paragraph, "table": number},
            )
        )

    def finish(self) -> list[ParsedSection]:
        self.flush()
        self._release_images("")
        if not self.sections and self.headings:
            # A document of headings only still has searchable text.
            self.sections.append(ParsedSection(self._path(), {"paragraph": 1}))
        return self.sections


def _is_caption(text: str) -> bool:
    """Whether a paragraph reads like a figure caption."""
    return bool(_CAPTION.match(text)) and len(text.split()) <= _MAX_CAPTION_WORDS


_TABLE_CAPTION = re.compile(r"^\s*(?:جدول|table)\s*[\d۰-۹(]", re.IGNORECASE)


def _is_table_caption(text: str) -> bool:
    """Whether a paragraph reads like a table caption ("جدول ۳-۶: ...")."""
    return bool(_TABLE_CAPTION.match(text)) and len(text.split()) <= _MAX_CAPTION_WORDS


def _parse_pptx_sections(
    file_bytes: bytes, notices: list[str], blobs: dict[int, bytes] | None = None
) -> list[ParsedSection]:
    """Extract traceable slide content and tables from PPTX bytes.

    Pictures are recognized several at a time before the slides are built;
    ``blobs`` receives each picture by its number in the presentation.
    """
    try:
        presentation = Presentation(io.BytesIO(file_bytes))
    except Exception as exc:
        raise DocumentError(
            "Corrupted or invalid PPTX document.", "corrupt_file"
        ) from exc
    settings = OCRSettings.from_environment().with_deadline()
    pictures = _pptx_pictures(presentation, notices) if settings.enabled else []
    readings = iter(recognize_images(pictures, settings, notices))
    if blobs is not None:
        blobs.update(
            (number, blob) for number, blob in enumerate(pictures, start=1) if blob
        )
    sections: list[ParsedSection] = []
    numbers = iter(range(1, len(pictures) + 1))
    for slide_index, slide in enumerate(presentation.slides, start=1):
        parts, images = _slide_content(slide, readings, numbers, settings.enabled)
        sections.extend(_slide_sections(slide_index, parts, images))
    return sections


def _slide_content(
    slide: Any, readings: Iterator[str], numbers: Iterator[int], ocr: bool
) -> tuple[list[str], list[tuple[int, str]]]:
    """A slide's text parts (with tables and notes) and its recognized pictures."""
    parts: list[str] = []
    images: list[tuple[int, str]] = []
    for shape in _slide_shapes(slide.shapes):
        if _is_pptx_layout_field(shape):
            continue
        if getattr(shape, "has_table", False):
            parts.append(_format_pptx_table(shape.table))
        elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE and ocr:
            number = next(numbers)
            text = next(readings)
            if text.strip():
                images.append((number, text.strip()))
        elif hasattr(shape, "text") and shape.text.strip() not in _PPTX_FIELD_TEXT:
            parts.append(shape.text.strip())
    if notes := _speaker_notes(slide):
        parts.append(f"[یادداشت سخنران]\n{notes}")
    return parts, images


def _slide_shapes(shapes: Any) -> Iterator[Any]:
    """Every shape of a slide, including those inside grouped shapes."""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _slide_shapes(shape.shapes)
        else:
            yield shape


def _speaker_notes(slide: Any) -> str:
    """The slide's speaker notes, which often hold most of a deck's prose."""
    if not slide.has_notes_slide:
        return ""
    frame = slide.notes_slide.notes_text_frame
    return frame.text.strip() if frame is not None else ""


# Slide number, date and footer placeholders repeat layout fields on every
# slide; an unrendered slide-number field reads as U+2039 # U+203A.
_PPTX_LAYOUT_FIELDS = frozenset(
    {PP_PLACEHOLDER.SLIDE_NUMBER, PP_PLACEHOLDER.DATE, PP_PLACEHOLDER.FOOTER}
)
_PPTX_FIELD_TEXT = frozenset({"", "\u2039#\u203a"})


def _is_pptx_layout_field(shape: Any) -> bool:
    """Whether a shape is a slide-number, date or footer placeholder."""
    return bool(
        shape.is_placeholder and shape.placeholder_format.type in _PPTX_LAYOUT_FIELDS
    )


def _slide_sections(
    slide_index: int, parts: list[str], images: list[tuple[int, str]]
) -> list[ParsedSection]:
    """One slide's text section, then one section per recognized picture."""
    sections: list[ParsedSection] = []
    if text := "\n\n".join(part for part in parts if part).strip():
        sections.append(ParsedSection(text, {"slide": slide_index}))
    # Each picture is its own section under the slide's title, so answers
    # can cite "slide N, image M" for text that only appears in the picture.
    slide_text = "\n".join(part for part in parts if part.strip())
    title, _, rest = slide_text.partition("\n")
    context = " ".join(rest.replace("\u2039#\u203a", " ").split())
    for number, recognized in images:
        body = _image_section_text(number, title, recognized, context)
        sections.append(ParsedSection(body, {"slide": slide_index, "image": number}))
    return sections


def _pptx_pictures(presentation: Any, notices: list[str]) -> list[bytes]:
    """Every picture of a presentation in slide and shape order.

    A linked picture (stored outside the file) has no image data; it keeps
    its number with empty bytes and a notice instead of rejecting the deck.
    """
    pictures: list[bytes] = []
    for slide in presentation.slides:
        for shape in _slide_shapes(slide.shapes):
            if getattr(shape, "has_table", False) or (
                shape.shape_type != MSO_SHAPE_TYPE.PICTURE
            ):
                continue
            try:
                pictures.append(shape.image.blob)
            except (ValueError, KeyError, AttributeError):
                pictures.append(b"")
                notices.append(NOTICE_OCR_PARTIAL)
    return pictures


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


def default_ocr_workers() -> int:
    """Images read at the same time when ``OCR_WORKERS`` is automatic.

    Every CPU this process may use, at most 8: OCR finishes before the
    document is embedded, so the two never compete for the CPU.
    """
    if hasattr(os, "sched_getaffinity"):
        available = len(os.sched_getaffinity(0))
    else:  # Windows and macOS have no affinity mask.
        available = os.cpu_count() or 1
    return max(1, min(8, available))


def ocr_workers() -> int:
    """Images recognized at the same time (``OCR_WORKERS``; default the CPUs, max 8).

    Each image is still read by its own Tesseract process with the same
    settings, so the text is the same as reading them one by one.
    """
    default = default_ocr_workers()
    try:
        value = int(os.getenv("OCR_WORKERS", "") or default)
    except ValueError:
        return default
    return min(16, max(1, value))


def recognize_images(
    images: list[bytes], settings: OCRSettings, notices: list[str]
) -> list[str]:
    """OCR Office images in document order; one text per image ("" if skipped).

    Images past ``OCR_MAX_IMAGES`` or images OCR cannot read only add a
    notice, so the rest of the document is still indexed.
    """
    within_budget = images[: settings.max_images]
    workers = min(ocr_workers(), len(within_budget))
    # Parallel Tesseract processes each use one thread instead of competing.
    active = replace(settings, single_thread=True) if workers > 1 else settings

    def read(image: bytes) -> tuple[str, str | None]:
        if not image or active.expired:
            return "", NOTICE_OCR_PARTIAL
        try:
            return extract_image_text(image, active), None
        except OCRUnavailableError:
            return "", NOTICE_OCR_UNAVAILABLE
        except (OCRError, ValueError):
            return "", NOTICE_OCR_PARTIAL

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(read, within_budget))
    else:
        results = [read(image) for image in within_budget]
    notices.extend(notice for _, notice in results if notice)
    if len(images) > len(within_budget):
        notices.append(NOTICE_OCR_IMAGE_LIMIT)
    return [text for text, _ in results] + [""] * (len(images) - len(within_budget))


def _parse_image_sections(
    file_bytes: bytes, blobs: dict[int, bytes] | None = None
) -> list[ParsedSection]:
    """Extract OCR text from a standalone raster image.

    The picture is image 1 of its file, so its source shows the image next to
    the excerpt, like pictures inside Word and PowerPoint.
    """
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
    if not text:
        return []
    if blobs is not None:
        blobs[1] = file_bytes
    return [ParsedSection(text, {"page": 1, "image": 1})]


_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")
# Below this share of Arabic-script letters, a Windows-1256 reading is not
# Persian/Arabic text and Windows-1252 (Western) is used instead.
_MIN_ARABIC_LETTER_SHARE = 0.3
# A UTF-8 file with a few stray bytes is still read as UTF-8 when it has at
# least this many valid non-ASCII characters per stray byte.
_UTF8_CHARACTERS_PER_STRAY_BYTE = 10


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
    # Mostly UTF-8 with a few stray bytes (a pasted Western character, a cut
    # file): reading it as Windows-1256 turned the whole file into mojibake.
    # Only text with real UTF-8 characters qualifies, so a legacy Western file
    # such as "café" in Windows-1252 still decodes as Windows-1252.
    lenient = file_bytes.decode("utf-8-sig", errors="replace")
    stray = lenient.count("\ufffd")
    multibyte = sum(ord(char) > 127 for char in lenient) - stray
    if multibyte >= _UTF8_CHARACTERS_PER_STRAY_BYTE * stray:
        return lenient.replace("\ufffd", "")
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
    elif filename.endswith((".csv", ".tsv")):
        return _delimited_table_sections(
            text, "\t" if filename.endswith(".tsv") else ","
        )
    elif filename.endswith((".html", ".htm", ".xml")):
        parser = _VisibleTextExtractor()
        parser.feed(text)
        text = "\n".join(
            line.strip() for line in "".join(parser.parts).splitlines() if line.strip()
        )
    text = text.strip()
    if not text:
        return []
    blocks = _text_blocks(text, markdown=filename.endswith((".md", ".markdown")))
    return [
        ParsedSection(block, {"section": number})
        for number, block in enumerate(blocks, start=1)
    ]


# Plain-text files were one "section 1", so every citation pointed at the
# whole file. They are now cut at Markdown headings or about this many words.
_TEXT_SECTION_WORDS = 300
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s")


def _text_blocks(text: str, *, markdown: bool) -> list[str]:
    """Split a text file into locatable sections without cutting lines."""
    blocks: list[str] = []
    current: list[str] = []
    words = 0
    for line in text.splitlines():
        heading = markdown and bool(_MARKDOWN_HEADING.match(line))
        line_words = len(line.split())
        if current and (heading or words + line_words > _TEXT_SECTION_WORDS):
            blocks.append("\n".join(current).strip())
            current, words = [], 0
        current.append(line)
        words += line_words
    if current:
        blocks.append("\n".join(current).strip())
    return [block for block in blocks if block]


def _delimited_table_sections(text: str, delimiter: str) -> list[ParsedSection]:
    """Read CSV/TSV as a table, so rows keep their headers and come back whole."""
    rows = [
        [_clean_cell_text(cell) for cell in row]
        for row in csv.reader(io.StringIO(text), delimiter=delimiter)
        if any(cell.strip() for cell in row)
    ]
    if not rows:
        return []
    width = max(len(row) for row in rows)
    grid = [row + [""] * (width - len(row)) for row in rows]
    return [ParsedSection(_format_table_grid(grid), {"table": 1})]


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


def _add_docx_table(
    builder: "_DocxSectionBuilder", table: Table, numbered: int, paragraph: int
) -> int:
    """Add a table after ``paragraph``; return the count of numbered tables.

    A one-cell table is a text box (often a command or code) that belongs
    with the sentence introducing it, not a table of its own.
    """
    box = _single_cell_text(table)
    if box is not None:
        if box:
            builder.paragraph(box, paragraph)
        return numbered
    value = _format_docx_table(table).strip()
    if value:
        builder.table(value, numbered + 1, paragraph)
    return numbered + 1


def _single_cell_text(table: Table) -> str | None:
    """The text of a table with exactly one cell, or None for a real table."""
    cells = {cell._tc: cell for row in table.rows for cell in row.cells}
    if len(cells) != 1:
        return None
    return str(next(iter(cells.values())).text).strip()


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


def _kept_text(text: str) -> str:
    """Native text worth keeping when a page could not be read with OCR."""
    return "" if text_layer_is_garbled(text) else text


def _combined_text(text: str, recognized: str) -> str:
    """Combine a page's native text with what OCR read from it."""
    if recognized and text_layer_is_garbled(text):
        return recognized
    if recognized and text and text not in recognized:
        return f"{text}\n\n{recognized}"
    return recognized or text


def _recognize_pages(
    images: list[bytes], settings: OCRSettings, notices: list[str]
) -> list[str | None]:
    """OCR rendered pages several at a time; None marks a page that failed.

    Pages left when the document's OCR time runs out are skipped with a
    notice, like pages that cannot be read.
    """
    workers = min(ocr_workers(), len(images))
    active = replace(settings, single_thread=True) if workers > 1 else settings

    def read(image: bytes) -> tuple[str | None, str | None]:
        if active.expired:
            return None, NOTICE_OCR_PARTIAL
        try:
            return recognize_page_png(image, active), None
        except OCRUnavailableError:
            # The text pages are still useful; the notice names the setup problem.
            return None, NOTICE_OCR_UNAVAILABLE
        except OCRError:
            return None, NOTICE_OCR_PARTIAL

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(read, images))
    else:
        results = [read(image) for image in images]
    notices.extend(notice for _, notice in results if notice)
    return [text for text, _ in results]


def _scan_pdf_pages(
    document: Any, settings: OCRSettings, notices: list[str]
) -> tuple[list[tuple[int, str]], dict[int, bytes]]:
    """Native text of every page, and the pages to OCR rendered as PNG."""
    pages: list[tuple[int, str]] = []
    rendered: dict[int, bytes] = {}
    scanned_pages = 0
    for page_number, page in enumerate(document, start=1):
        text = logical_page_text(page)
        pages.append((page_number, text))
        if not _needs_pdf_ocr(page, text, settings):
            continue
        scanned_pages += 1
        if not settings.enabled or scanned_pages > settings.max_pages:
            if settings.enabled:
                notices.append(NOTICE_OCR_PAGE_LIMIT)
            pages[-1] = (page_number, _kept_text(text))
            continue
        try:
            rendered[page_number] = render_page_png(page, settings)
        except OCRError:
            notices.append(NOTICE_OCR_PARTIAL)
            pages[-1] = (page_number, _kept_text(text))
    return pages, rendered


def _parse_pdf_sections(file_bytes: bytes, notices: list[str]) -> list[ParsedSection]:
    """Extract ordered PDF pages and OCR image pages with sparse text layers.

    Pages are rendered on this thread (PyMuPDF is not thread-safe) and then
    recognized several at a time, like images inside Word and PowerPoint.
    Pages past ``OCR_MAX_PAGES`` and pages OCR cannot read keep their native
    text (often empty) and add a notice instead of rejecting the document.
    """
    try:
        document = pymupdf.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise DocumentError(
            "Corrupted or invalid PDF document.", "corrupt_file"
        ) from exc
    if getattr(document, "needs_pass", False) is True:
        document.close()
        raise DocumentError("The PDF is password-protected.", "encrypted_document")

    settings = OCRSettings.from_environment().with_deadline()
    try:
        pages, rendered = _scan_pdf_pages(document, settings, notices)
    finally:
        document.close()

    numbers = list(rendered)
    readings = dict(
        zip(
            numbers,
            _recognize_pages(
                [rendered[number] for number in numbers], settings, notices
            ),
            strict=True,
        )
    )
    sections: list[ParsedSection] = []
    for page_number, text in pages:
        if page_number in readings:
            recognized = readings[page_number]
            text = (
                _kept_text(text)
                if recognized is None
                else _combined_text(text, recognized)
            )
        if text:
            sections.append(ParsedSection(text=text, metadata={"page": page_number}))
    return sections
