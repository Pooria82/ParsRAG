import pytest
from pydantic import ValidationError

from backend.core.models.domain import (
    ChatMessage,
    ExtractedNode,
    QueryMode,
    QueryRequest,
    QueryResponse,
)


def test_query_mode_enum() -> None:
    assert QueryMode.STRICT.value == "strict"
    assert QueryMode.HYBRID.value == "hybrid"
    assert QueryMode.LLM_ONLY.value == "llm-only"


def test_chat_message_valid() -> None:
    msg = ChatMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_chat_message_missing_fields() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(role="user")  # type: ignore[call-arg]


def test_llm_only_query_allows_no_session() -> None:
    req = QueryRequest(prompt="What is this?", mode=QueryMode.LLM_ONLY)
    assert req.prompt == "What is this?"
    assert req.chat_history == []
    assert req.mode == QueryMode.LLM_ONLY
    assert req.session_id is None


def test_query_request_custom() -> None:
    req = QueryRequest(
        prompt="Explain RAG",
        chat_history=[ChatMessage(role="user", content="Hi")],
        mode=QueryMode.STRICT,
        session_id="12345",
    )
    assert req.mode == QueryMode.STRICT
    assert req.session_id == "12345"
    assert len(req.chat_history) == 1


def test_document_query_requires_session_id() -> None:
    with pytest.raises(ValidationError, match="session_id is required"):
        QueryRequest(prompt="What is this?", mode=QueryMode.STRICT)


def test_extracted_node() -> None:
    node = ExtractedNode(text="Chunk 1", metadata={"page": 1}, score=0.95)
    assert node.text == "Chunk 1"
    assert node.metadata["page"] == 1
    assert node.score == 0.95


def test_query_response() -> None:
    node = ExtractedNode(text="Chunk 1")
    res = QueryResponse(answer="Here is the answer.", source_nodes=[node])
    assert res.answer == "Here is the answer."
    assert len(res.source_nodes) == 1
    assert res.source_nodes[0].text == "Chunk 1"
