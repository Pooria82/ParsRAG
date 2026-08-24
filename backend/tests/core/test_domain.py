import pytest
from pydantic import ValidationError

from backend.core.models.domain import (
    ChatMessage,
    DocumentIngestionRequest,
    ExtractedNode,
    QueryMode,
    QueryRequest,
    QueryResponse,
)


def test_query_mode_enum():
    assert QueryMode.STRICT == "strict"
    assert QueryMode.HYBRID == "hybrid"
    assert QueryMode.LLM_ONLY == "llm-only"


def test_chat_message_valid():
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_chat_message_missing_fields():
    with pytest.raises(ValidationError):
        ChatMessage(role="user")  # Missing content


def test_query_request_defaults():
    req = QueryRequest(prompt="What is this?")
    assert req.prompt == "What is this?"
    assert req.chat_history == []
    assert req.mode == QueryMode.HYBRID
    assert req.session_id is None


def test_query_request_custom():
    req = QueryRequest(
        prompt="Explain RAG",
        chat_history=[ChatMessage(role="user", content="Hi")],
        mode=QueryMode.STRICT,
        session_id="12345",
    )
    assert req.mode == QueryMode.STRICT
    assert req.session_id == "12345"
    assert len(req.chat_history) == 1


def test_document_ingestion_request():
    req = DocumentIngestionRequest(
        filename="test.pdf", file_bytes=b"fakebytes", session_id="abc"
    )
    assert req.filename == "test.pdf"
    assert req.file_bytes == b"fakebytes"
    assert req.session_id == "abc"


def test_extracted_node():
    node = ExtractedNode(text="Chunk 1", metadata={"page": 1}, score=0.95)
    assert node.text == "Chunk 1"
    assert node.metadata["page"] == 1
    assert node.score == 0.95


def test_query_response():
    node = ExtractedNode(text="Chunk 1")
    res = QueryResponse(answer="Here is the answer.", source_nodes=[node])
    assert res.answer == "Here is the answer."
    assert len(res.source_nodes) == 1
    assert res.source_nodes[0].text == "Chunk 1"
