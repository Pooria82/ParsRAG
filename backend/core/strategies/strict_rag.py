import os

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import QueryResponse
from backend.core.strategies.base_strategy import RAGStrategy

STRICT_RAG_PROMPT_TEMPLATE = """\
You are an AI assistant that strictly answers based on the provided context.
If the context does not contain the answer, you must respond with: "I do not know based on the provided documents."
Do not use your own external knowledge under any circumstances.
If the query asks to aggregate, list, or compare information dispersed across multiple sections or tables in the document, comprehensively gather and include all relevant facts found across all context sections.

Context:
{context_str}

Query: {query}
Answer:"""


class StrictRAGStrategy(RAGStrategy):
    """Executes a strict Retrieval-Augmented Generation strategy.

    This strategy only uses retrieved context to answer the user's question.
    If no relevant context is found, it refuses to answer.
    """

    def __init__(
        self,
        repo: AbstractDocumentRepository,
        default_top_k: int = 15,
    ) -> None:
        self.repo = repo
        self.threshold = float(os.getenv("STRICT_RAG_THRESHOLD", "0.75"))
        self.default_top_k = int(
            os.getenv("STRICT_RAG_TOP_K", os.getenv("RAG_TOP_K", str(default_top_k)))
        )
        self.prompt_template = PromptTemplate(STRICT_RAG_PROMPT_TEMPLATE)
        self.llm = Settings.llm

    def execute(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
    ) -> QueryResponse:
        """Executes the strict RAG pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for retrieval depth.

        Returns:
            QueryResponse: The generated answer or a refusal if context is insufficient.
        """
        # 1. Retrieve
        fetch_k = top_k if top_k is not None else self.default_top_k
        nodes = self.repo.similarity_search(query, top_k=fetch_k, session_id=session_id)

        # 2. Threshold Check
        if not nodes:
            return QueryResponse(
                answer="هیچ سند مرتبطی یافت نشد. (No relevant documents found.)",
                source_nodes=[],
            )

        # Check if the highest score passes our strict threshold
        highest_score = max(
            [n.score for n in nodes if n.score is not None], default=0.0
        )
        if highest_score < self.threshold:
            return QueryResponse(
                answer="بر اساس اسناد ارائه شده، پاسخی برای این سوال ندارم. (I do not know based on the provided documents.)",
                source_nodes=[],
            )

        # Adaptive relevance filtering:
        # Retain dispersed chunks that meet semantic quality while filtering out noise
        relevance_cutoff = max(0.55, highest_score * 0.70)
        filtered_nodes = [
            n for n in nodes if n.score is not None and n.score >= relevance_cutoff
        ]
        if not filtered_nodes:
            filtered_nodes = [nodes[0]]

        # 3. Synthesize with section-labeled context
        context_parts: list[str] = []
        for i, n in enumerate(filtered_nodes, start=1):
            source_tag = (
                f" [سند: {n.metadata.get('filename', '')}]"
                if n.metadata.get("filename")
                else ""
            )
            score_tag = f" (امتیاز: {n.score:.2f})" if n.score is not None else ""
            context_parts.append(f"--- بخش {i}{source_tag}{score_tag} ---\n{n.text}")

        context_str = "\n\n".join(context_parts)
        prompt = self.prompt_template.format(context_str=context_str, query=query)

        response = self.llm.complete(prompt)
        return QueryResponse(
            answer=str(response).strip(),
            source_nodes=filtered_nodes,
        )
