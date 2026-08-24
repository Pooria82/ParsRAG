"""
Custom domain exceptions for ParsRAG.
"""


class ParsRAGError(Exception):
    """Base exception for all ParsRAG errors."""



class VectorDBConnectionError(ParsRAGError):
    """Raised when the vector database connection fails or queries fail."""



class LLMInferenceTimeoutError(ParsRAGError):
    """Raised when the LLM takes too long to respond."""



class EmptyDocumentError(ParsRAGError):
    """Raised when a document contains no extractable text."""

