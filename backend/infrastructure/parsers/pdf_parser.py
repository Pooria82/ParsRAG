import fitz  # type: ignore  # PyMuPDF


class EmptyDocumentError(Exception):
    """Raised when a document contains no selectable text (e.g., scanned image)."""



def parse_pdf(file_bytes: bytes) -> str:
    """Extracts text content from a PDF file byte stream.

    Args:
        file_bytes (bytes): The raw bytes of the PDF file.

    Returns:
        str: The extracted text from all pages, concatenated.

    Raises:
        EmptyDocumentError: If the PDF contains no text.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        page_text = page.get_text("text")
        if page_text:
            text += page_text + "\n"

    doc.close()

    if not text.strip():
        raise EmptyDocumentError(
            "The document contains no selectable text. Scanned PDFs are not supported."
        )

    return text.strip()
