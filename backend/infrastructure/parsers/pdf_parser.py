import fitz  # PyMuPDF

class EmptyDocumentError(Exception):
    """Raised when a document contains no selectable text (e.g., scanned image)."""
    pass

def parse_pdf(file_bytes: bytes) -> str:
    """Parses a PDF from bytes and extracts raw text."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        page_text = page.get_text("text")
        if page_text:
            text += page_text + "\n"
        
    doc.close()
    
    if not text.strip():
        raise EmptyDocumentError("The document contains no selectable text. Scanned PDFs are not supported.")
        
    return text.strip()
