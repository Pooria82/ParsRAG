import logging
import math
import os
import re
import unicodedata
from math import ceil

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.exceptions import VectorDBConnectionError
from backend.core.dto.output.query import PreparedAnswer
from backend.core.port.document_repository import DocumentRepository
from backend.core.port.progress_tracker import ProgressCallback
from backend.core.service.context_budget import fit_to_context, model_context_window
from backend.core.service.retrieval_optimizer import (
    RetrievalOptimizer,
    configured_depth,
)
from backend.core.strategies.generation import GeneratingStrategy
from backend.core.strategies.multi_doc_utils import (
    distinct_passages,
    format_multi_doc_context,
    has_tagged_evidence,
    include_tagged_anchors,
    order_by_document,
    resolve_target_files,
    retrieve_document_nodes,
    retrieve_question_parts,
    with_part_evidence,
    with_whole_tables,
)
from backend.core.strategies.prompt_rules import (
    CITATION_RULES,
    CODE_VERIFICATION_RULES,
    FORMATTING_RULES,
    LANGUAGE_RULES,
    answer_language_rule,
    question_language,
)

logger = logging.getLogger("parsrag.operations")

STRICT_REFUSAL_FA = "بر اساس اسناد ارائه شده، پاسخی برای این سوال در متن یافت نشد."
STRICT_REFUSAL_EN = "I do not know based on the provided documents."

STRICT_RAG_PROMPT_TEMPLATE = (
    """You answer questions using ONLY the document excerpts in the context below.

GROUNDING RULES (documents-only mode):
1. Every fact, number, name, date, and claim in your answer must come from the context. Never add outside knowledge, assumptions, or examples that are not in the context.
2. The question may use different words, spelling, or language than the documents. Match by meaning, not by exact wording: paraphrase, translate, summarize, and combine information from several excerpts.
3. You may state conclusions that follow directly from the context, such as what kind of document it is, its main topic, or a comparison the user asks for, as long as you cite the excerpts they rest on.
4. When the question asks several things, answer each one. If the context answers only some of them, answer those, then say plainly which part the documents do not cover.
5. Only when nothing in the context is relevant to the question, reply with exactly one sentence:
"""
    + f'   - Persian: "{STRICT_REFUSAL_FA}"\n'
    + f'   - English: "{STRICT_REFUSAL_EN}"\n'
    + """6. OCR text may contain recognition errors. Read past obvious noise, but never invent a missing word, number, or relationship to repair it.

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

{answer_language}"""
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
# Words that name the document itself. A summary or topic word only makes a
# question about the whole document when it is tied to one of these, or when
# the request is nothing but "summarize" / "what is the main topic".
_DOCUMENT_NOUN = (
    r"(?:سند|اسناد|فایل(?:[\s\u200c]*ها)?|گزارش|متن|مقاله|نوشته|کتاب|ارائه"
    r"|اسلاید(?:[\s\u200c]*ها)?|pdf|پی[\s\u200c]*دی[\s\u200c]*اف)"
)
_THIS = r"(?:(?:این|کل|همه(?:[\s\u200c]*ی)?)\s*)?"
_SUMMARY_WORD = r"(?:خلاصه|چکیده|جمع[\s\u200c]*بندی|کلیات)"
DOCUMENT_OVERVIEW_PATTERN = re.compile(
    "|".join(
        (
            # «این سند درباره چیست؟»، «فایل در مورد چه است»
            _THIS
            + _DOCUMENT_NOUN
            + r"[\s\u200c]*(?:ها)?\s*(?:درباره|در\s*(?:مورد|باره))"
            r"[\s\u200c]*(?:ی)?\s*(?:چیست|چه)",
            # «موضوع اصلی این فایل»، «محتوای کلی گزارش»
            r"(?:موضوع|محتوا|محتوای)(?:[\s\u200c]*(?:اصلی|کلی))?[\s\u200c]*(?:ی|\u0654)?\s*"
            + _THIS
            + _DOCUMENT_NOUN,
            # «خلاصه‌ای از این گزارش»، «چکیده مقاله»
            _SUMMARY_WORD
            + r"[\s\u200c]*(?:ای|ی|\u0654)?\s*(?:از\s*)?"
            + _THIS
            + _DOCUMENT_NOUN,
            # «گزارش را خلاصه کن»
            _DOCUMENT_NOUN + r"\s*(?:را|رو)\s*(?:خلاصه|جمع[\s\u200c]*بندی)",
            # «این فایل چه نوع سندی است؟»، «نوع این سند»
            r"چه\s*نوع\s*(?:سندی|فایلی|متنی|گزارشی|" + _DOCUMENT_NOUN + r")",
            r"نوع\s*" + _THIS + _DOCUMENT_NOUN,
            # A bare request: «خلاصه کن»، «یک خلاصه بده»
            r"^\W*(?:لطفا|لطفاً)?\s*(?:یک\s*)?"
            + _SUMMARY_WORD
            + r"[\s\u200c]*(?:ای|اش|ش)?\s*(?:کن|بده|بنویس|بگو)?\W*$",
            r"^\W*موضوع(?:[\s\u200c]*اصلی)?\s*(?:چیست|چه\s*است|کدام\s*است)\W*$",
            # English
            r"\bsummar(?:y|ize|ise)\s+(?:of\s+)?(?:(?:this|the|these|all|each)\s+)?"
            r"(?:documents?|files?|reports?|papers?|pdfs?|slides?|texts?)\b",
            r"\bsummar(?:ize|ise)\s+(?:it|this|them)\b",
            r"^\W*(?:please\s+)?summar(?:ize|ise)\W*$",
            r"\b(?:overview|main\s+topic)\s+of\s+(?:this|the|these)\s+"
            r"(?:documents?|files?|reports?|papers?)\b",
            r"^\W*what\s+is\s+the\s+main\s+topic\W*$",
            r"\bwhat\s+(?:is|are)\s+(?:this|the|these)\s+"
            r"(?:documents?|files?|papers?|reports?|pdfs?)\s+about\b",
            r"\bwhat\s+kind\s+of\s+(?:document|file)\b",
        )
    ),
    re.IGNORECASE,
)


def configured_threshold() -> float:
    """Return ``STRICT_RAG_THRESHOLD`` between 0 and 1, or the default.

    An invalid value used to make every documents-only question fail while
    Settings showed the default; it now falls back to the default with a
    warning.
    """
    raw = os.getenv("STRICT_RAG_THRESHOLD", "").strip()
    if not raw:
        return DEFAULT_STRICT_THRESHOLD
    try:
        value = float(raw)
    except ValueError:
        value = math.nan
    if not 0.0 <= value <= 1.0:
        logger.warning(
            "STRICT_RAG_THRESHOLD=%r is not a number between 0 and 1; using %s",
            raw,
            DEFAULT_STRICT_THRESHOLD,
        )
        return DEFAULT_STRICT_THRESHOLD
    return value


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


class StrictRAGStrategy(GeneratingStrategy):
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
        self.threshold = configured_threshold()
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

    def prepare(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
        top_k: int | None = None,
        file_filter: list[str] | None = None,
        progress: ProgressCallback | None = None,
        document_segments: list[tuple[str, str]] | None = None,
        answer_language: str | None = None,
    ) -> PreparedAnswer:
        """Retrieve, apply the evidence gates, and build the grounded prompt.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for retrieval depth.
            file_filter (list[str] | None, optional): Optional list of filenames to restrict to.
            progress (ProgressCallback | None, optional): Reports retrieval and generation stages.
            document_segments: File-scoped question segments from explicit mentions.
            answer_language: ``"fa"`` or ``"en"``; by default the language of ``query``.

        Returns:
            PreparedAnswer: The prompt with numbered sources, or a refusal.
        """
        language = answer_language or question_language(query)
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
        # Each part of a question that asks several things is searched too.
        part_results = (
            []
            if document_segments
            else retrieve_question_parts(
                self.repo,
                query,
                available_files,
                effective_filter,
                session_id,
                max(4, fetch_k // 2),
            )
        )
        # Part results decide whether there is evidence and add each part's
        # best excerpts below; the main pool is not widened with all of them.
        evidence = (
            distinct_passages(
                [*nodes, *(node for found in part_results for node in found)]
            )
            if part_results
            else nodes
        )
        nodes = nodes or evidence

        # 3. Threshold Check
        persian = language == "fa"
        if not nodes:
            return PreparedAnswer(
                immediate=(
                    "هیچ سند مرتبطی یافت نشد."
                    if persian
                    else "No relevant documents found."
                ),
                outcome="no_documents",
            )

        highest_score = max(
            [n.score for n in evidence if n.score is not None], default=0.0
        )
        if (
            highest_score < self.threshold
            and not is_document_overview_question(query)
            and not _has_lexical_evidence(query, evidence, self.threshold)
        ):
            return PreparedAnswer(
                immediate=STRICT_REFUSAL_FA if persian else STRICT_REFUSAL_EN,
                outcome="no_evidence",
            )
        if document_segments and not has_tagged_evidence(
            nodes, document_segments, self.threshold
        ):
            return PreparedAnswer(
                immediate=(
                    "برای پاسخ بر اساس همه اسناد اشاره‌شده، شواهد کافی پیدا نشد."
                    if persian
                    else "Insufficient evidence across the mentioned documents."
                ),
                outcome="partial_evidence",
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

        filtered_nodes = with_part_evidence(
            filtered_nodes,
            part_results,
            per_part=3,
            minimum_score=max(0.55, self.threshold - 0.20),
        )
        filtered_nodes = with_whole_tables(self.repo, filtered_nodes, session_id)

        # 5. Build Grouped Multi-Document Context within the model's window
        language_rule = answer_language_rule(language)
        filtered_nodes = order_by_document(
            fit_to_context(
                filtered_nodes,
                context_window=model_context_window(self.llm),
                fixed_prompt=self.prompt_template.format(
                    context_str="", query=query, answer_language=language_rule
                ),
            )
        )
        context_str = format_multi_doc_context(filtered_nodes)
        prompt = self.prompt_template.format(
            context_str=context_str, query=query, answer_language=language_rule
        )
        return PreparedAnswer(prompt=prompt, sources=filtered_nodes)
