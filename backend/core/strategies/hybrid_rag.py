from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.exceptions import VectorDBConnectionError
from backend.core.dto.output.query import QueryResponse
from backend.core.port.document_repository import DocumentRepository
from backend.core.port.progress_tracker import ProgressCallback
from backend.core.port.query_strategy import QueryStrategy
from backend.core.port.reranker import Reranker
from backend.core.service.context_budget import fit_to_context, model_context_window
from backend.core.service.retrieval_optimizer import (
    RetrievalOptimizer,
    configured_depth,
)
from backend.core.strategies.multi_doc_utils import (
    format_multi_doc_context,
    resolve_target_files,
    retrieve_document_nodes,
)
from backend.core.strategies.prompt_rules import (
    CITATION_RULES,
    CODE_VERIFICATION_RULES,
    FORMATTING_RULES,
    LANGUAGE_RULES,
)

HYBRID_RAG_PROMPT_TEMPLATE = (
    """\
You are a knowledgeable assistant. Answer the user's question using the document excerpts in the context first.

SOURCE RULES (hybrid mode):
1. Prefer the context. When it contains relevant information, build the answer on it and cite it.
2. You may add general knowledge to explain, complete, or connect the documents' content. Make clear which statements come from the documents and which are general knowledge, and never attribute outside knowledge to a document.
3. If the documents and general knowledge disagree, say so and give the documents' version.
4. When summarizing, comparing, or concluding across documents, synthesize the key findings of each and state the overall conclusion.

"""
    + CODE_VERIFICATION_RULES
    + "\n\n"
    + CITATION_RULES
    + "\n\n"
    + LANGUAGE_RULES
    + "\n\n"
    + FORMATTING_RULES
    + """

Context:
{context_str}

Query: {query}
Answer:"""
)


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


class HybridRAGStrategy(QueryStrategy):
    """Executes a hybrid RAG strategy with fallback, reranking, and multi-file support.

    This strategy retrieves a broad candidate pool across the document collection
    (ensuring balanced representation when multiple files exist), reranks them
    with a cross-encoder, and synthesizes the answer.
    """

    def __init__(
        self,
        repo: DocumentRepository,
        top_k_retrieve: int | None = None,
        top_n_rerank: int | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        """Configure retrieval depth, reranking, and the active model adapter.

        Args:
            repo: The session-scoped document repository.
            top_k_retrieve: Minimum candidate pool; defaults to
                ``HYBRID_RETRIEVE_TOP_K`` or 25.
            top_n_rerank: Fixed reranked chunk count; defaults to
                ``HYBRID_RERANK_TOP_K`` when set, otherwise adaptive depth.
            reranker: Cross-encoder for the candidate pool; without one the
                dense similarity order is kept.
        """
        self.repo = repo
        self.reranker = reranker
        self.prompt_template = PromptTemplate(HYBRID_RAG_PROMPT_TEMPLATE)
        self.llm = Settings.llm
        self.default_retrieve_k = (
            top_k_retrieve
            if top_k_retrieve is not None
            else configured_depth("HYBRID_RETRIEVE_TOP_K") or 25
        )
        self.default_rerank_n = (
            top_n_rerank
            if top_n_rerank is not None
            else configured_depth("HYBRID_RERANK_TOP_K")
        )

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
        rerank_n = top_k if top_k is not None else self.default_rerank_n
        if rerank_n is None:
            rerank_n = RetrievalOptimizer.calculate_optimal_depth(
                query, available_files
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

        # 4. Rerank the candidate pool (dense order when no reranker is set)
        if self.reranker is not None:
            reranked_source_nodes = self.reranker.rerank(
                query, extracted_nodes, rerank_n
            )
        else:
            reranked_source_nodes = sorted(
                extracted_nodes, key=lambda node: node.score or 0.0, reverse=True
            )[:rerank_n]

        # 5. Build Grouped Multi-Document Context
        final_source_nodes = _merge_evidence(
            extracted_nodes,
            reranked_source_nodes,
            limit=rerank_n,
            min_anchors=max(3, len({filename for filename, _ in document_segments}))
            if document_segments
            else 3,
        )

        final_source_nodes = fit_to_context(
            final_source_nodes,
            context_window=model_context_window(self.llm),
            fixed_prompt=self.prompt_template.format(context_str="", query=query),
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
