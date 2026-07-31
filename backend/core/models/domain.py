from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class QueryMode(str, Enum):
    STRICT = "strict"
    HYBRID = "hybrid"
    LLM_ONLY = "llm-only"

class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the sender (e.g., 'user', 'assistant')")
    content: str = Field(..., description="Content of the message")

class QueryRequest(BaseModel):
    prompt: str = Field(..., description="The user's query")
    chat_history: List[ChatMessage] = Field(default_factory=list, description="Previous conversation history")
    mode: QueryMode = Field(default=QueryMode.HYBRID, description="The RAG execution mode")
    session_id: Optional[str] = Field(default=None, description="Optional session ID for scoped retrieval")

class DocumentIngestionRequest(BaseModel):
    filename: str = Field(..., description="Name of the file being ingested")
    file_bytes: bytes = Field(..., description="Raw bytes of the file")
    session_id: Optional[str] = Field(default=None, description="Optional session ID to scope the document")

class ExtractedNode(BaseModel):
    text: str = Field(..., description="The chunked text content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata like page number and source file")
    score: Optional[float] = Field(default=None, description="Relevance score from retrieval or reranking")

class QueryResponse(BaseModel):
    answer: str = Field(..., description="The generated response from the LLM")
    source_nodes: List[ExtractedNode] = Field(default_factory=list, description="Citations and source chunks used")
