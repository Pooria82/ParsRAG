import os

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

from backend.core.models.domain import QueryResponse
from backend.core.strategies.base_strategy import RAGStrategy
from backend.core.interfaces.repository import AbstractDocumentRepository

STRICT_RAG_PROMPT_TEMPLATE = """\
You are an AI assistant that strictly answers based on the provided context.
If the context does not contain the answer, you must respond with: "I do not know based on the provided documents."
Do not use your own external knowledge under any circumstances.

Context:
{context_str}

Query: {query}
Answer:"""


class StrictRAGStrategy(RAGStrategy):
    """Executes a strict Retrieval-Augmented Generation strategy.

    This strategy only uses retrieved context to answer the user's question.
    If no relevant context is found, it refuses to answer.
    """

    def __init__(self, repo: AbstractDocumentRepository):
        self.repo = repo
        self.threshold = float(os.getenv("STRICT_RAG_THRESHOLD", "0.75"))
        self.prompt_template = PromptTemplate(STRICT_RAG_PROMPT_TEMPLATE)
        self.llm = Settings.llm

    def execute(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
    ) -> QueryResponse:
        """Executes the strict RAG pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.

        Returns:
            QueryResponse: The generated answer or a refusal if context is insufficient.
        """
        # 1. Retrieve
        nodes = self.repo.similarity_search(query, top_k=5, session_id=session_id)

        # 2. Threshold Check
        if not nodes:
            return QueryResponse(answer="هیچ سند مرتبطی یافت نشد. (No relevant documents found.)")

        # Check if the highest score passes our threshold
        # Qdrant cosine similarity typically ranges from -1 to 1 or 0 to 1 depending on distance metric.
        highest_score = max(
            [n.score for n in nodes if n.score is not None], default=0.0
        )
        if highest_score < self.threshold:
            return QueryResponse(answer="بر اساس اسناد ارائه شده، پاسخی برای این سوال ندارم. (I do not know based on the provided documents.)")

        # 3. Synthesize
        context_str = "\n\n".join([n.text for n in nodes])
        prompt = self.prompt_template.format(context_str=context_str, query=query)

        response = self.llm.complete(prompt)
        return QueryResponse(answer=str(response).strip())
