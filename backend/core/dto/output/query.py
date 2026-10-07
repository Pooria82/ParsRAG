"""Outbound DTOs for question answering."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.enums import QueryStage

AnswerOutcome = Literal["answered", "no_documents", "no_evidence", "partial_evidence"]


class QueryResponse(BaseModel):
    """Generated answer and the document chunks that supported it."""

    answer: str = Field(..., description="The generated response from the LLM")
    outcome: AnswerOutcome = Field(
        default="answered",
        description="answered, or why no answer was generated (no_documents, "
        "no_evidence, partial_evidence) so clients can explain it",
    )
    source_nodes: list[ExtractedNode] = Field(
        default_factory=list,
        description="Excerpts given to the model, numbered [1]..[n] in this order",
    )
    cited: list[int] = Field(
        default_factory=list,
        description="1-based numbers of the source_nodes the answer cites",
    )


@dataclass(frozen=True)
class PreparedAnswer:
    """Retrieval result: a prompt to generate from, or a final reply without one.

    ``sources`` are numbered [1]..[n] in the prompt in this order.
    """

    prompt: str | None = None
    sources: list[ExtractedNode] = field(default_factory=list)
    immediate: str = ""
    outcome: AnswerOutcome = "answered"


class QueryProgressResponse(BaseModel):
    """A coarse, non-sensitive pipeline stage for one in-flight query."""

    stage: QueryStage
