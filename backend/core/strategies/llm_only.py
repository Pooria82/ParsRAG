from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

from backend.core.dto.output.query import QueryResponse
from backend.core.port.progress_tracker import ProgressCallback
from backend.core.port.query_strategy import QueryStrategy
from backend.core.strategies.prompt_rules import FORMATTING_RULES, LANGUAGE_RULES

LLM_ONLY_PROMPT_TEMPLATE = (
    """\
You are a helpful assistant. Answer the user's question directly from your general knowledge.

"""
    + LANGUAGE_RULES
    + "\n\n"
    + FORMATTING_RULES
    + """

Query: {query}
Answer:"""
)


class LLMOnlyStrategy(QueryStrategy):
    """Executes a pure LLM strategy without any retrieval.

    This strategy answers the user's question relying solely on the LLM's
    internal knowledge and provided chat history.
    """

    def __init__(self) -> None:
        """Bind the active language model and model-only prompt."""
        self.prompt_template = PromptTemplate(LLM_ONLY_PROMPT_TEMPLATE)
        self.llm = Settings.llm

    def execute(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
        file_filter: list[str] | None = None,
        progress: ProgressCallback | None = None,
        document_segments: list[tuple[str, str]] | None = None,
    ) -> QueryResponse:
        """Executes the LLM-only pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): Ignored in this strategy.
            top_k (int | None, optional): Ignored in this strategy.
            file_filter (list[str] | None, optional): Ignored in this strategy.
            progress (ProgressCallback | None, optional): Reports model generation.
            document_segments: Ignored in this strategy.

        Returns:
            QueryResponse: The LLM's raw answer.
        """
        # Note: In a chat scenario, you could pass the full chat history directly to self.llm.chat()
        # but since the query is already condensed, we just pass the query.
        if progress:
            progress("generating")
        prompt = self.prompt_template.format(query=query)
        response = self.llm.complete(prompt)
        return QueryResponse(answer=str(response).strip())
