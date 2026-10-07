"""Domain and application errors raised by the framework-agnostic core.

Infrastructure failures derive from ``ParsRAGError``. Use-case outcomes that a
driving adapter must translate for its caller derive from ``ApplicationError``;
the HTTP adapter maps each subclass to one status code without the core
importing a web framework.

Every error carries a stable machine-readable ``code`` so clients can show a
specific, translated explanation instead of one generic failure message.
"""

from typing import Any


class ParsRAGError(Exception):
    """Base exception for all ParsRAG errors."""

    code = "service_error"


class VectorDBConnectionError(ParsRAGError):
    """Raised when the vector database connection fails or queries fail."""

    code = "vector_store_unavailable"


class LLMInferenceTimeoutError(ParsRAGError):
    """Raised when the LLM takes too long to respond."""

    code = "model_timeout"


class EmptyDocumentError(ParsRAGError):
    """Raised when a document contains no extractable text."""

    code = "empty_document"

    def __init__(self, detail: str, code: str | None = None) -> None:
        """Store the message and the specific reason (e.g. OCR disabled)."""
        super().__init__(detail)
        if code is not None:
            self.code = code


class ModelConnectionError(ParsRAGError):
    """Raised when a model service cannot be verified, reached, or saved."""

    code = "model_unavailable"


class DocumentError(ValueError):
    """A document cannot be read; ``code`` names the reason for clients."""

    def __init__(self, detail: str, code: str) -> None:
        """Store the message and its stable reason code."""
        super().__init__(detail)
        self.code = code


class ApplicationError(Exception):
    """A use-case outcome that callers must receive as a safe, explicit error."""

    code = "invalid_request"

    def __init__(self, detail: Any, code: str | None = None) -> None:
        """Store the caller-visible detail and code without internal context."""
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code


class InvalidInputError(ApplicationError):
    """The request is well-formed but violates a business rule."""


class NotFoundError(ApplicationError):
    """A referenced session resource does not exist."""

    code = "not_found"


class ConflictError(ApplicationError):
    """The request conflicts with the current session state."""

    code = "conflict"


class PayloadTooLargeError(ApplicationError):
    """An upload exceeds a configured size boundary."""

    code = "too_large"


class CapacityExceededError(ApplicationError):
    """Every execution slot for an expensive operation is occupied."""

    code = "busy"


class UpstreamServiceError(ApplicationError):
    """A required external service could not be reached."""

    code = "upstream_unavailable"
