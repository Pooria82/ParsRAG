import os
import re
import unicodedata
from math import ceil

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.exceptions import VectorDBConnectionError
from backend.core.dto.output.query import QueryResponse
from backend.core.port.document_repository import DocumentRepository
from backend.core.port.progress_tracker import ProgressCallback
from backend.core.port.query_strategy import QueryStrategy
from backend.core.service.retrieval_optimizer import (
    RetrievalOptimizer,
    configured_depth,
)
from backend.core.strategies.multi_doc_utils import (
    format_multi_doc_context,
    has_tagged_evidence,
    include_tagged_anchors,
    resolve_target_files,
    retrieve_document_nodes,
)
from backend.core.strategies.prompt_rules import (
    CITATION_RULES,
    CODE_VERIFICATION_RULES,
    FORMATTING_RULES,
    LANGUAGE_RULES,
)

STRICT_REFUSAL_FA = "بر اساس اسناد ارائه شده، پاسخی برای این سوال در متن یافت نشد."
STRICT_REFUSAL_EN = "I do not know based on the provided documents."

STRICT_RAG_PROMPT_TEMPLATE = (
    """You answer questions using ONLY the document excerpts in the context below.

GROUNDING RULES (documents-only mode):
1. Every fact, number, name, date, and claim in your answer must come from the context. Never add outside knowledge, assumptions, or examples that are not in the context.
2. The question may use different words, spelling, or language than the documents. Match by meaning, not by exact wording: paraphrase, translate, summarize, and combine information from several excerpts.
3. You may state conclusions that follow directly from the context, such as what kind of document it is, its main topic, or a comparison the user asks for, as long as you cite the excerpts they rest on.
4. If the context answers only part of the question, answer that part, then say briefly which part the documents do not cover.
5. Only when nothing in the context is relevant to the question, reply with exactly one sentence:
   - Persian: "بر اساس اسناد ارائه شده، پاسخی برای این سوال در متن یافت نشد."
   - English: "I do not know based on the provided documents."
6. OCR text may contain recognition errors. Read past obvious noise, but never invent a missing word, number, or relationship to repair it.

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

DEFAULT_STRICT_THRESHOLD = 0.75
_WORD = re.compile(r"[^\W_]{3,}", re.UNICODE)
_QUERY_STOPWORDS = {
    "and",
    "are",
    "based",
    "does",
    "from",
    "how",
    "the",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "چه",
    "چگونه",
    "چیست",
    "است",
    "این",
    "آن",
    "برای",
    "درباره",
    "براساس",
    "اسناد",
    "سند",
    "صفحه",
    "های",
    "در",
    "از",
    "به",
    "را",
    "که",
    "آیا",
    "کن",
    "بگو",
    "کرده",
    "شده",
}


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
DOCUMENT_OVERVIEW_PATTERN = re.compile(
    r"(درباره\s*(?:چیست|چه|ی\s*چیست)|موضوع(?:\s*اصلی)?|خلاصه|چکیده|جمع[\s\u200c]*بندی"
    r"|کلیات|چه\s*نوع|نوع\s*(?:سند|فایل)|محتوای\s*(?:کلی|اصلی)"
    r"|\b(?:summar(?:y|ize|ise)|overview|main\s+topic|what\s+is\s+(?:this|the)\s+"
    r"(?:document|file|paper|report|pdf)\s+about|what\s+kind\s+of\s+document)\b)",
    re.IGNORECASE,
)


def is_document_overview_question(query: str) -> bool:
    """Return whether a question asks about a document as a whole.

    Such questions (topic, type, summary) are answerable from any retrieved
    content, so their similarity scores do not reflect answerability.
    """
    return bool(DOCUMENT_OVERVIEW_PATTERN.search(query))


def _evidence_terms(value: str) -> set[str]:
    """Extract distinctive multilingual words for a conservative text check."""
    normalized = unicodedata.normalize("NFKC", value.lower())
    normalized = normalized.replace("ي", "ی").replace("ك", "ک").replace("\u200c", "")
    normalized = normalized.translate(_DIGITS)
    return set(_WORD.findall(normalized)) - _QUERY_STOPWORDS


def _has_lexical_evidence(
    query: str, nodes: list[ExtractedNode], threshold: float
) -> bool:
    """Allow borderline vectors only when their text supports most query terms."""
    terms = _evidence_terms(query)
    if len(terms) < 2:
        return False
    minimum_score = max(0.55, threshold - 0.20)
    candidates = [
        node for node in nodes if node.score is not None and node.score >= minimum_score
    ][:5]
    if not candidates:
        return False
    evidence = _evidence_terms(" ".join(node.text for node in candidates))
    return len(terms & evidence) >= max(2, ceil(len(terms) * 0.6))


class StrictRAGStrategy(QueryStrategy):
    """Executes a strict Retrieval-Augmented Generation strategy.

    This strategy only uses retrieved context to answer the user's question.
    Supports targeted single-document queries and balanced multi-document
    retrieval across up to 10 files per session.
    """

    def __init__(
        self,
        repo: DocumentRepository,
        default_top_k: int | None = None,
    ) -> None:
        """Configure the repository, evidence threshold, depth, and active model.

        Args:
            repo: The session-scoped document repository.
            default_top_k: Fixed retrieval depth; defaults to ``STRICT_RAG_TOP_K``
                or ``RAG_TOP_K`` when set, otherwise adaptive depth is used.
        """
        self.repo = repo
        self.threshold = float(
            os.getenv("STRICT_RAG_THRESHOLD", "").strip() or DEFAULT_STRICT_THRESHOLD
        )
        self.default_top_k = (
            default_top_k
            if default_top_k is not None
            else configured_depth("STRICT_RAG_TOP_K", "RAG_TOP_K")
        )
        self.prompt_template = PromptTemplate(STRICT_RAG_PROMPT_TEMPLATE)
        self.llm = Settings.llm

    def _retrieval_depth(
        self, top_k: int | None, query: str, available_files: list[str]
    ) -> int:
        """Prefer the request depth, then the configured depth, then adaptive."""
        if top_k is not None:
            return top_k
        if self.default_top_k is not None:
            return self.default_top_k
        return RetrievalOptimizer.calculate_optimal_depth(query, available_files)

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
        """Executes the strict RAG pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for retrieval depth.
            file_filter (list[str] | None, optional): Optional list of filenames to restrict to.
            progress (ProgressCallback | None, optional): Reports retrieval and generation stages.
            document_segments: File-scoped question segments from explicit mentions.

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
        fetch_k = self._retrieval_depth(top_k, query, available_files)

        # 2. Retrieve Nodes (Balanced Multi-File vs. Single-File Search)
        nodes = retrieve_document_nodes(
            self.repo,
            query,
            available_files,
            effective_filter,
            session_id,
            fetch_k,
            3,
            document_segments,
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
        if (
            highest_score < self.threshold
            and not is_document_overview_question(query)
            and not _has_lexical_evidence(query, nodes, self.threshold)
        ):
            return QueryResponse(
                answer="بر اساس اسناد ارائه شده، پاسخی برای این سوال ندارم. (I do not know based on the provided documents.)",
                source_nodes=[],
            )
        if document_segments and not has_tagged_evidence(
            nodes, document_segments, self.threshold
        ):
            return QueryResponse(
                answer="برای پاسخ بر اساس همه اسناد اشاره‌شده، شواهد کافی پیدا نشد. (Insufficient evidence across the mentioned documents.)",
                source_nodes=[],
            )

        # 4. Adaptive Relevance Filtering
        relevance_cutoff = max(0.55, highest_score * 0.70)
        cutoff = (
            max(relevance_cutoff, self.threshold)
            if document_segments
            else relevance_cutoff
        )
        filtered_nodes = [n for n in nodes if n.score is not None and n.score >= cutoff]
        if not filtered_nodes:
            filtered_nodes = [nodes[0]]
        if document_segments:
            filtered_nodes = include_tagged_anchors(
                nodes, filtered_nodes, document_segments, self.threshold
            )

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
