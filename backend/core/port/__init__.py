"""Contracts the core requires from driven adapters.

Ports are structural ``typing.Protocol`` types: adapters satisfy them by shape,
and mypy verifies conformance wherever an adapter is wired into a use case.
"""

from backend.core.port.document_parser import DocumentParser
from backend.core.port.document_repository import DocumentRepository
from backend.core.port.model_gateway import ModelGateway
from backend.core.port.progress_tracker import ProgressCallback, ProgressTracker
from backend.core.port.query_strategy import QueryStrategy
from backend.core.port.question_condenser import QuestionCondenser
from backend.core.port.text_chunker import TextChunker

__all__ = [
    "DocumentParser",
    "DocumentRepository",
    "ModelGateway",
    "ProgressCallback",
    "ProgressTracker",
    "QueryStrategy",
    "QuestionCondenser",
    "TextChunker",
]
