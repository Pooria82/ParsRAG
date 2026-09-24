import os

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.postprocessor.flashrank_rerank import FlashRankRerank  # type: ignore

from backend.core.exceptions import VectorDBConnectionError
from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import ExtractedNode, QueryResponse
from backend.core.query_progress import ProgressCallback
from backend.core.retrieval_optimizer import RetrievalOptimizer
from backend.core.strategies.base_strategy import RAGStrategy
from backend.core.strategies.multi_doc_utils import (
    format_multi_doc_context,
    resolve_target_files,
    retrieve_document_nodes,
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


def _node_identity(node: ExtractedNode) -> tuple[str, str, object]:
    """Build a stable identity for deduplicating dense and reranked evidence."""
    return (
        node.text,
        str(node.metadata.get("filename", "")),
        node.metadata.get("page", node.metadata.get("section")),
    )


def _select_dense_anchors(
    nodes: list[ExtractedNode], *, limit: int
) -> list[ExtractedNode]:
    """Keep the strongest multilingual vector hits across distinct files."""
    if limit <= 0:
        return []
    ranked = sorted(nodes, key=lambda node: node.score or 0.0, reverse=True)
    anchors: list[ExtractedNode] = []
    used_files: set[str] = set()
    for node in ranked:
        filename = str(node.metadata.get("filename", ""))
        if filename and filename not in used_files:
            anchors.append(node)
            used_files.add(filename)
            if len(anchors) == limit:
                return anchors
    used_nodes = {_node_identity(node) for node in anchors}
    for node in ranked:
        if _node_identity(node) not in used_nodes:
            anchors.append(node)
            used_nodes.add(_node_identity(node))
            if len(anchors) == limit:
                break
    return anchors


def _merge_evidence(
    dense_nodes: list[ExtractedNode],
    reranked_nodes: list[ExtractedNode],
    *,
    limit: int,
    min_anchors: int = 3,
) -> list[ExtractedNode]:
    """Protect multilingual dense hits while retaining cross-encoder ordering."""
    anchors = _select_dense_anchors(dense_nodes, limit=min(min_anchors, limit))
    merged: list[ExtractedNode] = []
    seen: set[tuple[str, str, object]] = set()
    for node in [*anchors, *reranked_nodes]:
        identity = _node_identity(node)
        if identity in seen:
            continue
        merged.append(node)
        seen.add(identity)
        if len(merged) == limit:
            break
    return merged


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
        """Configure retrieval depth, reranking, and the active model adapter."""
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
        progress: ProgressCallback | None = None,
        document_segments: list[tuple[str, str]] | None = None,
    ) -> QueryResponse:
        """Executes the hybrid RAG pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for number of reranked chunks.
            file_filter (list[str] | None, optional): Optional list of filenames to restrict to.
            progress (ProgressCallback | None, optional): Reports retrieval and generation stages.
            document_segments: File-scoped question segments from explicit mentions.

        Returns:
            QueryResponse: The generated answer and source citations.
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
        rerank_n = (
            top_k
            if top_k is not None
            else RetrievalOptimizer.calculate_optimal_depth(query, available_files)
        )
        if document_segments:
            rerank_n = max(
                rerank_n, len({filename for filename, _ in document_segments})
            )
        retrieve_k = max(rerank_n * 2, self.default_retrieve_k)

        # 3. Broad Candidate Retrieval
        extracted_nodes = retrieve_document_nodes(
            self.repo,
            query,
            available_files,
            effective_filter,
            session_id,
            retrieve_k,
            5,
            document_segments,
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
        reranked_source_nodes: list[ExtractedNode] = []
        for n in reranked_nodes:
            text = n.get_content()
            metadata = n.node.metadata if hasattr(n.node, "metadata") else {}
            score = n.score
            reranked_source_nodes.append(
                ExtractedNode(text=text, metadata=metadata, score=score)
            )

        final_source_nodes = _merge_evidence(
            extracted_nodes,
            reranked_source_nodes,
            limit=rerank_n,
            min_anchors=max(3, len({filename for filename, _ in document_segments}))
            if document_segments
            else 3,
        )

        context_str = format_multi_doc_context(final_source_nodes)
        prompt = self.prompt_template.format(context_str=context_str, query=query)

        if progress:
            progress("generating")
        response = self.llm.complete(prompt)
        return QueryResponse(
            answer=str(response).strip(),
            source_nodes=final_source_nodes,
        )
