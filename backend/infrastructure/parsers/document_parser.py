import io
import fitz  # type: ignore  # PyMuPDF
from docx import Document  # type: ignore


class EmptyDocumentError(Exception):
    """Raised when a document contains no selectable text (e.g., scanned image)."""


def parse_document(file_bytes: bytes, filename: str) -> str:
    """Extracts text content from a PDF or DOCX file byte stream.

    Args:
        file_bytes (bytes): The raw bytes of the file.
        filename (str): The name of the file to determine its type.

    Returns:
        str: The extracted text from the document.

    Raises:
        EmptyDocumentError: If the document contains no text.
        ValueError: If the file format is unsupported.
    """
    if filename.lower().endswith(".pdf"):
        return _parse_pdf(file_bytes)
    elif filename.lower().endswith(".docx"):
        return _parse_docx(file_bytes)
    else:
        raise ValueError("Unsupported file format. Only PDF and DOCX are supported.")


def _parse_pdf(file_bytes: bytes) -> str:
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


def _parse_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    text = ""
    for para in doc.paragraphs:
        if para.text:
            text += para.text + "\n"
            
    if not text.strip():
        raise EmptyDocumentError("The DOCX document contains no text.")
        
    return text.strip()
