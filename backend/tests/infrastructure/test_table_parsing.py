import io

from docx import Document
from pptx import Presentation
from pptx.util import Inches

from backend.infrastructure.parsers.chunker import chunk_text
from backend.infrastructure.parsers.document_parser import parse_document


def create_synthetic_docx() -> bytes:
    """Creates a synthetic DOCX with paragraphs, wide tables, and merged cells."""
    doc = Document()
    doc.add_paragraph("مقدمه سند تست جداول پیچیده.")

    # 1. Add a wide and complex table (6 columns, 3 rows)
    table = doc.add_table(rows=3, cols=6)
    headers = [
        "شناسه",
        "نام ماژول",
        "مسئول",
        "وضعیت اجرا",
        "سطح اولویت",
        "توضیحات تکمیلی",
    ]
    for idx, h in enumerate(headers):
        table.rows[0].cells[idx].text = h

    row1_vals = [
        "MOD-01",
        "احراز هویت",
        "تیم امنیت",
        "موفق",
        "بحرانی",
        "تست نفوذ انجام شد",
    ]
    for idx, val in enumerate(row1_vals):
        table.rows[1].cells[idx].text = val

    row2_vals = [
        "MOD-02",
        "پایگاه داده",
        "تیم زیرساخت",
        "در حال انتظار",
        "بالا",
        "نیاز به تنظیم شاخص‌ها",
    ]
    for idx, val in enumerate(row2_vals):
        table.rows[2].cells[idx].text = val

    doc.add_paragraph("پاراگراف میانی بین دو جدول.")

    # 2. Add a 1x1 callout box
    callout = doc.add_table(rows=1, cols=1)
    callout.rows[0].cells[0].text = "توجه: این یک کادر هشدار یا کد نمونه است."

    doc.add_paragraph("نتیجه‌گیری پایانی.")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def create_synthetic_pptx() -> bytes:
    """Creates a synthetic PPTX with text and table shapes."""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank layout

    # Add a table shape (3 rows, 3 columns)
    shape = slide.shapes.add_table(
        rows=3, cols=3, left=Inches(1), top=Inches(1), width=Inches(6), height=Inches(3)
    )
    table = shape.table
    table.cell(0, 0).text = "کد"
    table.cell(0, 1).text = "عنوان"
    table.cell(0, 2).text = "امتیاز"

    table.cell(1, 0).text = "A1"
    table.cell(1, 1).text = "بخش یک"
    table.cell(1, 2).text = "95"

    table.cell(2, 0).text = "B2"
    table.cell(2, 1).text = "بخش دو"
    table.cell(2, 2).text = "88"

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


def test_docx_complex_table_parsing() -> None:
    """Verifies that wide DOCX tables are extracted with Markdown layout and row records."""
    file_bytes = create_synthetic_docx()
    text = parse_document(file_bytes, "test_table.docx")

    # Chronological flow verification
    assert "مقدمه سند تست جداول پیچیده." in text
    assert "پاراگراف میانی بین دو جدول." in text
    assert "نتیجه‌گیری پایانی." in text

    # Markdown table structure verification
    assert (
        "| شناسه | نام ماژول | مسئول | وضعیت اجرا | سطح اولویت | توضیحات تکمیلی |"
        in text
    )
    assert "| :--- | :--- | :--- | :--- | :--- | :--- |" in text
    assert (
        "| MOD-01 | احراز هویت | تیم امنیت | موفق | بحرانی | تست نفوذ انجام شد |"
        in text
    )

    # Structured row records verification (prevents lost headers upon chunk split)
    assert "[سوابق ردیف‌های جدول]:" in text
    assert (
        "- سطر 1: [شناسه]: MOD-01 | [نام ماژول]: احراز هویت | [مسئول]: تیم امنیت"
        in text
    )
    assert (
        "- سطر 2: [شناسه]: MOD-02 | [نام ماژول]: پایگاه داده | [مسئول]: تیم زیرساخت"
        in text
    )

    # Callout box verification
    assert "> [کادر محتوا]:" in text
    assert "توجه: این یک کادر هشدار یا کد نمونه است." in text


def test_pptx_table_parsing() -> None:
    """Verifies that PPTX tables are formatted as structured tables."""
    file_bytes = create_synthetic_pptx()
    text = parse_document(file_bytes, "presentation.pptx")

    assert "--- اسلاید 1 ---" in text
    assert "| کد | عنوان | امتیاز |" in text
    assert "| A1 | بخش یک | 95 |" in text
    assert "[سوابق ردیف‌های جدول]:" in text
    assert "[کد]: A1" in text


def test_table_chunking_preserves_row_context() -> None:
    """Verifies that when text containing complex tables is chunked, row records keep column associations."""
    file_bytes = create_synthetic_docx()
    text = parse_document(file_bytes, "test_table.docx")

    nodes = chunk_text(
        text, metadata={"filename": "test_table.docx"}, chunk_size=200, chunk_overlap=20
    )
    assert len(nodes) >= 2

    # Check that at least one chunk contains structured row records with explicit header pairings
    found_row_record = False
    for node in nodes:
        if "[شناسه]: MOD-01" in node.text and "[نام ماژول]: احراز هویت" in node.text:
            found_row_record = True
            break

    assert found_row_record, (
        "Chunking should retain structured row records with header associations."
    )
