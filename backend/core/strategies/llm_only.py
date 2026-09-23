from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

from backend.core.models.domain import QueryResponse
from backend.core.query_progress import ProgressCallback
from backend.core.strategies.base_strategy import RAGStrategy

LLM_ONLY_PROMPT_TEMPLATE = """\
You are a helpful AI assistant. Answer the user's question directly.

MANDATORY LANGUAGE RULES:
1. Match the natural language used by the user in their question:
   - If the user's question is in Persian (فارسی), respond entirely in Persian.
   - If the user's question is in English, respond in English.
   - CRITICAL: Programming code snippets, technical commands, function names, and technical terminology are almost always in English. Do NOT consider the presence of English code or technical terms as an English query. Always determine the target language from the user's surrounding natural language sentences and intent.
2. Under NO circumstances output in Chinese (中文) or any unintended language.

Query: {query}
Answer:"""


class LLMOnlyStrategy(RAGStrategy):
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
    ) -> QueryResponse:
        """Executes the LLM-only pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): Ignored in this strategy.
            top_k (int | None, optional): Ignored in this strategy.
            file_filter (list[str] | None, optional): Ignored in this strategy.
            progress (ProgressCallback | None, optional): Reports model generation.

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
