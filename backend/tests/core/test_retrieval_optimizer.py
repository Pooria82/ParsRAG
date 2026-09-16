"""Automated unit tests for the Dynamic Retrieval Depth Optimizer."""

import pytest

from backend.core.retrieval_optimizer import RetrievalOptimizer


def test_base_depth_for_standard_query() -> None:
    """Standard query with no triggers yields the base depth."""
    query = "نحوه راه‌اندازی سرور"
    depth = RetrievalOptimizer.calculate_optimal_depth(query)
    assert depth == RetrievalOptimizer.BASE_TOP_K
    assert depth == 12


@pytest.mark.parametrize(
    ("query", "expected_min_depth"),
    [
        ("خلاصه جامع از متن ارائه دهید", 22),
        ("چکیده و نتیجه‌گیری فصل دوم چیست؟", 22),
        ("مقایسه دو سیستم و بررسی تفاوت‌ها", 22),
        ("تمام عوامل و راهکارها را فهرست کن", 20),
        ("جدول داده‌های آماری و ارقام فروش", 20),
    ],
)
def test_intent_based_depth_expansion(query: str, expected_min_depth: int) -> None:
    """Broad intent triggers (summary, comparison, tables, enumeration) expand depth."""
    depth = RetrievalOptimizer.calculate_optimal_depth(query)
    assert depth >= expected_min_depth
    assert depth <= RetrievalOptimizer.MAX_TOP_K


def test_pinpoint_factoid_narrows_depth() -> None:
    """Targeted factoid query reduces depth below base depth."""
    query = "تاریخ جلسه کی است؟"
    depth = RetrievalOptimizer.calculate_optimal_depth(query)
    assert depth == 9  # Base 12 - 3 = 9
    assert depth >= RetrievalOptimizer.MIN_TOP_K


def test_compound_and_lengthy_query_expansion() -> None:
    """Long query containing compound connectors expands retrieval depth."""
    query = (
        "بررسی ساختار کلی سیستم و همچنین ارزیابی معماری سرویس‌ها "
        "با در نظر گرفتن تمامی جزئیات فنی و عملیاتی در فازهای مختلف پروژه"
    )
    depth = RetrievalOptimizer.calculate_optimal_depth(query)
    # 15+ words (+4) + connector 'و همچنین' (+3) + enumeration 'تمامی' (+8) -> Base 12 + 15 = 27
    assert depth >= 25
    assert depth <= RetrievalOptimizer.MAX_TOP_K


def test_multi_file_scaling() -> None:
    """Sessions with multiple files scale retrieval candidates proportionally."""
    files = ["doc1.docx", "doc2.docx", "doc3.docx", "doc4.docx"]
    # 4 files * 5 chunks/file = 20
    query = "توضیحات سیستم"
    depth = RetrievalOptimizer.calculate_optimal_depth(query, available_files=files)
    assert depth >= 20


def test_max_boundary_clamping() -> None:
    """Depth is clamped to MAX_TOP_K even with multiple intense triggers and 5 files."""
    files = [f"doc_{i}.docx" for i in range(5)]
    query = (
        "خلاصه و مقایسه جامع تمام آمار و ارقام و جداول و همچنین کلیه راهکارها "
        "با ارائه لیست کامل و جمع‌بندی نهایی از هر پنج سند"
    )
    depth = RetrievalOptimizer.calculate_optimal_depth(query, available_files=files)
    assert depth == RetrievalOptimizer.MAX_TOP_K
    assert depth == 30


def test_min_boundary_clamping() -> None:
    """Depth never drops below MIN_TOP_K (8 chunks)."""
    # Factoid query with minimal length
    query = "کد چیست؟"
    depth = RetrievalOptimizer.calculate_optimal_depth(query)
    assert depth >= RetrievalOptimizer.MIN_TOP_K
    assert depth >= 8
