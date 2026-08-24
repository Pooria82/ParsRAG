import pytest

from unittest.mock import MagicMock, patch

from backend.infrastructure.parsers.chunker import chunk_text
from backend.infrastructure.parsers.pdf_parser import EmptyDocumentError, parse_pdf

@patch("backend.infrastructure.parsers.pdf_parser.fitz.open")
def test_parse_empty_pdf(mock_fitz_open) -> None:
    # Mock a PDF document with one page but no text
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = ""
    
    # Doc behaves like an iterator of pages
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz_open.return_value = mock_doc

    with pytest.raises(EmptyDocumentError, match="The document contains no selectable text"):
        parse_pdf(b"fake pdf bytes")
    
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
