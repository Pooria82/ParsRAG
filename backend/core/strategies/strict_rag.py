import os

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

from backend.core.exceptions import VectorDBConnectionError
from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import ExtractedNode, QueryResponse
from backend.core.strategies.base_strategy import RAGStrategy
from backend.core.strategies.multi_doc_utils import (
    format_multi_doc_context,
    resolve_target_files,
)

STRICT_RAG_PROMPT_TEMPLATE = """\
You are an AI assistant that strictly answers based on the provided context.
If the context does not contain the answer, you must respond with: "I do not know based on the provided documents."
Do not use your own external knowledge under any circumstances.
If multiple documents are provided in the context:
- If asked to summarize, compare, or draw conclusions across the documents, synthesize the facts from each document comprehensively and state the overarching conclusion clearly.
- If asked about a specific document, focus your answer on that document while citing the document name where relevant.

Context:
{context_str}

Query: {query}
Answer:"""


class StrictRAGStrategy(RAGStrategy):
    """Executes a strict Retrieval-Augmented Generation strategy.

    This strategy only uses retrieved context to answer the user's question.
    Supports targeted single-document queries and balanced multi-document
    retrieval across up to 5 files per session.
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
        file_filter: list[str] | None = None,
    ) -> QueryResponse:
        """Executes the strict RAG pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for retrieval depth.
            file_filter (list[str] | None, optional): Optional list of filenames to restrict to.

        Returns:
            QueryResponse: The generated answer or a refusal if context is insufficient.
        """
        fetch_k = top_k if top_k is not None else self.default_top_k

        # 1. Discover session files to determine single-file vs multi-file path
        available_files: list[str] = []
        if session_id:
            try:
                available_files = self.repo.get_session_files(session_id)
            except VectorDBConnectionError:
                available_files = []

        effective_filter = resolve_target_files(
            query, available_files, explicit_filter=file_filter
        )

        # 2. Retrieve Nodes (Balanced Multi-File vs. Single-File Search)
        nodes: list[ExtractedNode] = []
        if len(available_files) > 1 and effective_filter is None:
            # Multi-document balanced retrieval: fetch top chunks per document
            k_per_file = max(3, fetch_k // len(available_files))
            for fn in available_files:
                file_nodes = self.repo.similarity_search(
                    query,
                    top_k=k_per_file,
                    session_id=session_id,
                    file_filter=[fn],
                )
                nodes.extend(file_nodes)
        else:
            nodes = self.repo.similarity_search(
                query,
                top_k=fetch_k,
                session_id=session_id,
                file_filter=effective_filter,
            )

        # 3. Threshold Check
        if not nodes:
            return QueryResponse(
                answer="هیچ سند مرتبطی یافت نشد. (No relevant documents found.)",
                source_nodes=[],
            )

        highest_score = max(
            [n.score for n in nodes if n.score is not None], default=0.0
        )
        if highest_score < self.threshold:
            return QueryResponse(
                answer="بر اساس اسناد ارائه شده، پاسخی برای این سوال ندارم. (I do not know based on the provided documents.)",
                source_nodes=[],
            )

        # 4. Adaptive Relevance Filtering
        relevance_cutoff = max(0.55, highest_score * 0.70)
        filtered_nodes = [
            n for n in nodes if n.score is not None and n.score >= relevance_cutoff
        ]
        if not filtered_nodes:
            filtered_nodes = [nodes[0]]

        # 5. Build Grouped Multi-Document Context
        context_str = format_multi_doc_context(filtered_nodes)
        prompt = self.prompt_template.format(context_str=context_str, query=query)

        response = self.llm.complete(prompt)
        return QueryResponse(
            answer=str(response).strip(),
            source_nodes=filtered_nodes,
        )
