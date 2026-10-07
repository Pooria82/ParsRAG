"""Dynamic and automatic retrieval depth (Top-K) optimization engine.

Analyzes query intent, semantic complexity, and session document cardinality
to dynamically determine the optimal chunk retrieval depth for RAG strategies.
"""

import re

# Intent Detection Regex Patterns (Persian & Multilingual)
SUMMARY_PATTERN = re.compile(
    r"\b(خلاصه|جمع‌بندی|چکیده|تحلیل کلی|نتیجه‌گیری|سنتز|خلاصه‌ای|برآیند|مرور کلی)\b",
    re.IGNORECASE,
)

COMPARISON_PATTERN = re.compile(
    r"\b(مقایسه|تفاوت|شباهت|بررسی تطبیقی|وجوه افتراق|تفاوت‌ها|شباهت‌ها|نسبت به هم)\b",
    re.IGNORECASE,
)

ENUMERATION_PATTERN = re.compile(
    r"\b(همه|تمام|تمامی|کلیه|فهرست|لیست|انواع|سوابق|اقلام|مراحل|عوامل|راهکارها|موارد)\b",
    re.IGNORECASE,
)

TABULAR_PATTERN = re.compile(
    r"\b(جدول|جداول|جدول‌های|آمار|ارقام|درصد|شاخص|مبلغ|ارزش|ستون|سطر|ردیف|داده‌های آماری)\b",
    re.IGNORECASE,
)

FACTOID_PATTERN = re.compile(
    r"\b(چقدر است|کی|تاریخ|کجا|چه کسی|شماره|تلفن|کد|ایمیل|آدرس|نام مدیر)\b",
    re.IGNORECASE,
)

COMPOUND_CONNECTOR_PATTERN = re.compile(
    r"\b(و همچنین|علاوه بر این|از طرفی|ضمن اینکه|به علاوه|از سوی دیگر)\b",
    re.IGNORECASE,
)


class RetrievalOptimizer:
    """Calculates optimal retrieval and aggregation depth (Top-K) per query."""

    MIN_TOP_K: int = 8
    MAX_TOP_K: int = 30
    BASE_TOP_K: int = 12

    @classmethod
    def calculate_optimal_depth(
        cls,
        query: str,
        available_files: list[str] | None = None,
    ) -> int:
        """Dynamically computes the optimal chunk retrieval depth for a query.

        Args:
            query: The user's input query or condensed question.
            available_files: Optional list of document filenames in the session.

        Returns:
            int: Optimal chunk retrieval depth clamped between MIN_TOP_K and MAX_TOP_K.
        """
        clean_query = query.strip()
        depth = cls.BASE_TOP_K
        files = available_files or []
        num_files = len(files)

        # 1. Multi-Document Scaling
        if num_files > 1:
            # Guarantee at least 5 chunks per file across the collection
            multi_file_requirement = num_files * 5
            depth = max(depth, multi_file_requirement)

        # 2. Query Intent Adjustments
        is_summary = bool(SUMMARY_PATTERN.search(clean_query))
        is_comparison = bool(COMPARISON_PATTERN.search(clean_query))
        is_enumeration = bool(ENUMERATION_PATTERN.search(clean_query))
        is_tabular = bool(TABULAR_PATTERN.search(clean_query))
        is_factoid = bool(FACTOID_PATTERN.search(clean_query))

        if is_summary:
            depth += 10
        if is_comparison:
            depth += 10
        if is_enumeration:
            depth += 8
        if is_tabular:
            depth += 8

        # If it's a pinpoint factoid without broad modifiers, narrow down
        if is_factoid and not (is_summary or is_comparison or is_enumeration):
            depth -= 3

        # 3. Query Complexity & Length Adjustments
        words = clean_query.split()
        if len(words) >= 15:
            depth += 4
        if COMPOUND_CONNECTOR_PATTERN.search(clean_query):
            depth += 3

        # 4. Clamp to operational bounds [8, 30]
        optimal_k = max(cls.MIN_TOP_K, min(cls.MAX_TOP_K, depth))
        return optimal_k
