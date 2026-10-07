"""Port for rewriting follow-up questions into standalone retrieval queries."""

from typing import Protocol

from llama_index.core.llms import ChatMessage


class QuestionCondenser(Protocol):
    """Resolve pronouns and references using the prior conversation."""

    def condense(self, query: str, chat_history: list[ChatMessage]) -> str:
        """Return a standalone question, or the query itself without history."""
        ...
