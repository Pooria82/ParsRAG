import os

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.postprocessor.flashrank_rerank import FlashRankRerank  # type: ignore

from backend.core.exceptions import VectorDBConnectionError
from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import ExtractedNode, QueryResponse
from backend.core.retrieval_optimizer import RetrievalOptimizer
from backend.core.strategies.base_strategy import RAGStrategy
from backend.core.strategies.multi_doc_utils import (
    format_multi_doc_context,
    resolve_target_files,
)

HYBRID_RAG_PROMPT_TEMPLATE = """\
You are an intelligent AI assistant. Use the provided context to answer the user's question.
If the context contains relevant information, synthesize the answer comprehensively.

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

DOCUMENT SYNTHESIS RULES:
- If asked to summarize, compare, or draw conclusions across documents, synthesize key findings from each document and state the overall conclusion clearly.
- If asked about a specific document, focus your answer on that document while citing the document name where relevant.
- When a source label includes a page, slide, paragraph, or section, append that exact source label at the end of the relevant answer paragraph. Never invent a location.

Context:
{context_str}

Query: {query}
Answer:"""


class HybridRAGStrategy(RAGStrategy):
    """Executes a hybrid RAG strategy with fallback, reranking, and multi-file support.

    This strategy retrieves a broad candidate pool across the document collection
    (ensuring balanced representation when multiple files exist), reranks them
    using FlashRank, and synthesizes the answer.
    """

    def __init__(
        self,
        repo: AbstractDocumentRepository,
        top_k_retrieve: int | None = None,
        top_n_rerank: int | None = None,
    ) -> None:
        self.repo = repo
        self.prompt_template = PromptTemplate(HYBRID_RAG_PROMPT_TEMPLATE)
        self.llm = Settings.llm
        self.default_retrieve_k = (
            top_k_retrieve
            if top_k_retrieve is not None
            else int(os.getenv("HYBRID_RETRIEVE_TOP_K", "25"))
        )
        self.default_rerank_n = (
            top_n_rerank
            if top_n_rerank is not None
            else int(os.getenv("HYBRID_RERANK_TOP_K", "15"))
        )
        self.reranker = FlashRankRerank(top_n=self.default_rerank_n)

    def execute(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
        file_filter: list[str] | None = None,
    ) -> QueryResponse:
        """Executes the hybrid RAG pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for number of reranked chunks.
            file_filter (list[str] | None, optional): Optional list of filenames to restrict to.

        Returns:
            QueryResponse: The generated answer and source citations.
        """
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
        rerank_n = (
            top_k
            if top_k is not None
            else RetrievalOptimizer.calculate_optimal_depth(query, available_files)
        )
        retrieve_k = max(rerank_n * 2, self.default_retrieve_k)

        # 3. Broad Candidate Retrieval
        extracted_nodes: list[ExtractedNode] = []
        if len(available_files) > 1 and effective_filter is None:
            # Multi-document balanced candidate retrieval
            k_per_file = max(5, retrieve_k // len(available_files))
            for fn in available_files:
                file_nodes = self.repo.similarity_search(
                    query,
                    top_k=k_per_file,
                    session_id=session_id,
                    file_filter=[fn],
                )
                extracted_nodes.extend(file_nodes)
        else:
            extracted_nodes = self.repo.similarity_search(
                query,
                top_k=retrieve_k,
                session_id=session_id,
                file_filter=effective_filter,
            )

        if not extracted_nodes:
            return QueryResponse(
                answer="هیچ سند مرتبطی یافت نشد. (No relevant documents found.)",
                source_nodes=[],
            )

        # 3. Map to LlamaIndex Node structures for reranking
        nodes_with_score = [
            NodeWithScore(
                node=TextNode(text=n.text, metadata=n.metadata),
                score=n.score or 0.0,
            )
            for n in extracted_nodes
        ]

        # 4. Rerank
        reranker = (
            FlashRankRerank(top_n=rerank_n)
            if rerank_n != self.default_rerank_n
            else self.reranker
        )
        query_bundle = QueryBundle(query_str=query)
        reranked_nodes = reranker.postprocess_nodes(
            nodes_with_score, query_bundle=query_bundle
        )

        # 5. Build Grouped Multi-Document Context
        final_source_nodes: list[ExtractedNode] = []
        for n in reranked_nodes:
            text = n.get_content()
            metadata = n.node.metadata if hasattr(n.node, "metadata") else {}
            score = n.score
            final_source_nodes.append(
                ExtractedNode(text=text, metadata=metadata, score=score)
            )

        context_str = format_multi_doc_context(final_source_nodes)
        prompt = self.prompt_template.format(context_str=context_str, query=query)

        response = self.llm.complete(prompt)
        return QueryResponse(
            answer=str(response).strip(),
            source_nodes=final_source_nodes,
        )
