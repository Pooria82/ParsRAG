import pytest

from backend.infrastructure.parsers.chunker import chunk_text
from backend.infrastructure.parsers.pdf_parser import parse_pdf


def test_parse_empty_pdf():
    # Since we don't have a real PDF byte stream here, we will just simulate a failure
    # if empty bytes are passed. In fitz, opening empty bytes raises an exception.
    # A better mock would be to mock fitz.open.
    with pytest.raises(Exception):  # noqa: B017
        parse_pdf(b"")


def test_chunk_text():
    # Simulate a Persian text
    persian_text = "این یک متن تستی برای سیستم پردازش زبان طبیعی پارس رگ است. " * 50
    nodes = chunk_text(persian_text, metadata={"source": "test.txt"})

    assert len(nodes) > 0
    assert nodes[0].metadata["source"] == "test.txt"
    # Ensure splitting happened (50 sentences should be split into multiple chunks)
    assert len(nodes) > 1
    assert len(nodes[0].text) > 0
