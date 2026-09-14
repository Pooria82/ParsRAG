import os
from unittest.mock import MagicMock, patch

import pytest

from backend.infrastructure.parsers.chunker import chunk_text
from backend.infrastructure.parsers.document_parser import EmptyDocumentError, parse_document


@patch("backend.infrastructure.parsers.document_parser.fitz.open")
def test_parse_empty_pdf(mock_fitz_open: MagicMock) -> None:
    # Mock a PDF document with one page but no text
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = ""
    
    # Doc behaves like an iterator of pages
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz_open.return_value = mock_doc

    with pytest.raises(EmptyDocumentError, match="The document contains no selectable text"):
        parse_document(b"fake pdf bytes", "fake.pdf")
    
    mock_doc.close.assert_called_once()


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
    file_path = os.path.join(os.path.dirname(__file__), "../../../data/نیازمندی‌های تست.docx")
    
    if not os.path.exists(file_path):
        pytest.skip("Test file 'نیازمندی‌های تست.docx' not found in data/ directory.")
        
    with open(file_path, "rb") as f:
        file_bytes = f.read()
        
    text = parse_document(file_bytes, "نیازمندی‌های تست.docx")
    assert len(text) > 0
    assert "تست" in text
