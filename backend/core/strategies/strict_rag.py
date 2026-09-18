import os

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

from backend.core.exceptions import VectorDBConnectionError
from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import ExtractedNode, QueryResponse
from backend.core.query_progress import ProgressCallback
from backend.core.retrieval_optimizer import RetrievalOptimizer
from backend.core.strategies.base_strategy import RAGStrategy
from backend.core.strategies.multi_doc_utils import (
    format_multi_doc_context,
    resolve_target_files,
)

STRICT_RAG_PROMPT_TEMPLATE = """\
You are an expert AI assistant that strictly answers based on the provided context.
Do not use your own external knowledge under any circumstances.

MANDATORY LANGUAGE RULES:
1. Match the natural language used by the user in their question:
   - If the user's question is in Persian (فارسی), respond entirely in Persian.
   - If the user's question is in English, respond in English.
   - CRITICAL: Programming code snippets, technical commands, function names, and technical terminology are almost always in English. Do NOT consider the presence of English code or technical terms as an English query. Always determine the target language from the user's surrounding natural language sentences and intent.
2. Under NO circumstances output in Chinese (中文) or any unintended language.

CONTENT & CODE VERIFICATION RULES:
1. If the user asks whether a specific code snippet, function, command, library, or concept is mentioned in the documents:
   - Compare the code conceptually, structurally, and functionally against the context.
   - Ignore minor syntax or formatting differences such as missing parentheses, whitespace, omitted variable declarations (e.g. var/let/const), or shortened/rephrased comments.
   - If the core methods, API calls, or logic exist in the context, explicitly confirm:
     * In Persian: "بله، این اطلاعات/کد در سند وجود دارد"
     * In English: "Yes, this information/code is present in the document"
     and quote the relevant snippet from the document, explaining its section or context.
2. If the context does not contain the answer, respond strictly with:
   - In Persian: "بر اساس اسناد ارائه شده، پاسخی برای این سوال در متن یافت نشد. (I do not know based on the provided documents.)"
   - In English: "I do not know based on the provided documents."

DOCUMENT SYNTHESIS RULES:
- If asked to summarize, compare, or draw conclusions across documents, synthesize the facts comprehensively and state the overarching conclusion clearly.
- If asked about a specific document, focus your answer on that document while citing the document name where relevant.
- When a source label includes a page, slide, paragraph, or section, append that exact source label at the end of the relevant answer paragraph. Never invent a location.

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
        """Configure the repository, evidence threshold, and active model."""
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
        progress: ProgressCallback | None = None,
    ) -> QueryResponse:
        """Executes the strict RAG pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for retrieval depth.
            file_filter (list[str] | None, optional): Optional list of filenames to restrict to.
            progress (ProgressCallback | None, optional): Reports retrieval and generation stages.

        Returns:
            QueryResponse: The generated answer or a refusal if context is insufficient.
        """
        if progress:
            progress("retrieving")

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

        # 2. Determine Optimal Retrieval Depth (Dynamic Optimizer)
        fetch_k = (
            top_k
            if top_k is not None
            else RetrievalOptimizer.calculate_optimal_depth(query, available_files)
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

        if progress:
            progress("generating")
        response = self.llm.complete(prompt)
        return QueryResponse(
            answer=str(response).strip(),
            source_nodes=filtered_nodes,
        )
