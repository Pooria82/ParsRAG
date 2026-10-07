"""Domain and application errors raised by the framework-agnostic core.

Infrastructure failures derive from ``ParsRAGError``. Use-case outcomes that a
driving adapter must translate for its caller derive from ``ApplicationError``;
the HTTP adapter maps each subclass to one status code without the core
importing a web framework.
"""

from typing import Any


class ParsRAGError(Exception):
    """Base exception for all ParsRAG errors."""


class VectorDBConnectionError(ParsRAGError):
    """Raised when the vector database connection fails or queries fail."""


class LLMInferenceTimeoutError(ParsRAGError):
    """Raised when the LLM takes too long to respond."""


class EmptyDocumentError(ParsRAGError):
    """Raised when a document contains no extractable text."""


class ModelConnectionError(ParsRAGError):
    """Raised when a model service cannot be verified, reached, or saved."""


class ApplicationError(Exception):
    """A use-case outcome that callers must receive as a safe, explicit error."""

    def __init__(self, detail: Any) -> None:
        """Store the caller-visible detail without internal context."""
        super().__init__(detail)
        self.detail = detail


class InvalidInputError(ApplicationError):
    """The request is well-formed but violates a business rule."""


class NotFoundError(ApplicationError):
    """A referenced session resource does not exist."""


class ConflictError(ApplicationError):
    """The request conflicts with the current session state."""


class PayloadTooLargeError(ApplicationError):
    """An upload exceeds a configured size boundary."""


class CapacityExceededError(ApplicationError):
    """Every execution slot for an expensive operation is occupied."""


class UpstreamServiceError(ApplicationError):
    """A required external service could not be reached."""
