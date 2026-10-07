"""Outbound DTOs for question answering."""

from pydantic import BaseModel, Field

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.enums import QueryStage


class QueryResponse(BaseModel):
    """Generated answer and the document chunks that supported it."""

    answer: str = Field(..., description="The generated response from the LLM")
    source_nodes: list[ExtractedNode] = Field(
        default_factory=list,
        description="Excerpts given to the model, numbered [1]..[n] in this order",
    )
    cited: list[int] = Field(
        default_factory=list,
        description="1-based numbers of the source_nodes the answer cites",
    )


class QueryProgressResponse(BaseModel):
    """A coarse, non-sensitive pipeline stage for one in-flight query."""

    stage: QueryStage
