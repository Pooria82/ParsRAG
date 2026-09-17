from unittest.mock import MagicMock, patch

from llama_index.core.llms import ChatMessage, MessageRole

from backend.core.condenser import CondenseQuestionPipeline
from backend.core.models.domain import ExtractedNode
from backend.core.strategies.hybrid_rag import HybridRAGStrategy
from backend.core.strategies.llm_only import LLMOnlyStrategy
from backend.core.strategies.strict_rag import StrictRAGStrategy


@patch("backend.core.condenser.Settings")
def test_condense_question(mock_settings: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.complete.return_value = "پایتخت ایران کجاست؟"
    mock_settings.llm = mock_llm

    condenser = CondenseQuestionPipeline()
    history = [
        ChatMessage(role=MessageRole.USER, content="درباره ایران بگو"),
        ChatMessage(
            role=MessageRole.ASSISTANT, content="ایران کشوری در خاورمیانه است."
        ),
    ]

    condensed = condenser.condense("پایتخت آن کجاست؟", history)
    assert condensed == "پایتخت ایران کجاست؟"
    mock_llm.complete.assert_called_once()


@patch("backend.core.strategies.strict_rag.Settings")
def test_strict_rag_below_threshold(mock_settings: MagicMock) -> None:
    mock_repo = MagicMock()
    # Return nodes with score 0.5 (below default 0.75)
    mock_repo.similarity_search.return_value = [
        ExtractedNode(text="Some text", score=0.5)
    ]

    strategy = StrictRAGStrategy(mock_repo)
    result = strategy.execute("test query", [])

    assert "I do not know" in result.answer or "ندارم" in result.answer
    mock_settings.llm.complete.assert_not_called()


@patch("backend.core.strategies.strict_rag.Settings")
def test_strict_rag_above_threshold(mock_settings: MagicMock) -> None:
    mock_repo = MagicMock()
    # Return nodes with score 0.9 (above default 0.75)
    mock_repo.similarity_search.return_value = [
        ExtractedNode(text="High quality text", score=0.9)
    ]

    mock_llm = MagicMock()
    mock_llm.complete.return_value = "The correct answer."
    mock_settings.llm = mock_llm

    strategy = StrictRAGStrategy(mock_repo)
    result = strategy.execute("test query", [])

    assert result.answer == "The correct answer."
    mock_llm.complete.assert_called_once()


@patch("backend.core.strategies.llm_only.Settings")
def test_llm_only_strategy(mock_settings: MagicMock) -> None:
    mock_llm = MagicMock()
    mock_llm.complete.return_value = "General answer"
    mock_settings.llm = mock_llm

    strategy = LLMOnlyStrategy()
    result = strategy.execute("query", [])

    assert result.answer == "General answer"
    mock_llm.complete.assert_called_once()


@patch("backend.core.strategies.hybrid_rag.FlashRankRerank")
@patch("backend.core.strategies.hybrid_rag.Settings")
def test_hybrid_rag_strategy(
    mock_settings: MagicMock, mock_rerank_cls: MagicMock
) -> None:
    mock_repo = MagicMock()
    mock_repo.similarity_search.return_value = [
        ExtractedNode(text="raw text", score=0.6)
    ]

    mock_rerank = MagicMock()
    # Mock reranked node structure
    from llama_index.core.schema import NodeWithScore, TextNode

    mock_rerank.postprocess_nodes.return_value = [
        NodeWithScore(node=TextNode(text="reranked text"), score=0.9)
    ]
    mock_rerank_cls.return_value = mock_rerank

    mock_llm = MagicMock()
    mock_llm.complete.return_value = "Hybrid answer"
    mock_settings.llm = mock_llm

    strategy = HybridRAGStrategy(mock_repo)
    result = strategy.execute("query", [])

    assert result.answer == "Hybrid answer"
    assert len(result.source_nodes) == 1
    mock_repo.similarity_search.assert_called_once()
    mock_rerank.postprocess_nodes.assert_called_once()
    mock_llm.complete.assert_called_once()


@patch("backend.core.strategies.strict_rag.Settings")
def test_strict_rag_multi_chunk_dispersed_aggregation(
    mock_settings: MagicMock,
) -> None:
    """Verifies that multiple dispersed chunks across a document are aggregated without truncation."""
    mock_repo = MagicMock()
    # Simulate 10 dispersed sections across a 200-page document with good scores + 1 noise chunk
    dispersed_nodes = [
        ExtractedNode(
            text=f"بخش {i}: اطلاعات فاز {i} پروژه.",
            score=0.85 - (i * 0.01),
            metadata={"filename": "large_report.docx", "section": i},
        )
        for i in range(1, 11)
    ]
    # Add a low-relevance noise chunk
    dispersed_nodes.append(
        ExtractedNode(text="متن کاملاً بی‌ربط", score=0.40, metadata={})
    )

    mock_repo.similarity_search.return_value = dispersed_nodes

    mock_llm = MagicMock()
    mock_llm.complete.return_value = "گزارش تجمیعی فازهای ۱ تا ۱۰."
    mock_settings.llm = mock_llm

    strategy = StrictRAGStrategy(mock_repo, default_top_k=15)
    result = strategy.execute(
        "اطلاعات تمام فازها را جمع‌آوری کن",
        [],
        top_k=15,
    )

    # All 10 valid dispersed sections should be passed, while the 0.40 noise chunk is filtered out
    assert len(result.source_nodes) == 10
    assert result.answer == "گزارش تجمیعی فازهای ۱ تا ۱۰."
    mock_llm.complete.assert_called_once()
    called_prompt = mock_llm.complete.call_args[0][0]
    for i in range(1, 11):
        assert f"بخش {i}: اطلاعات فاز {i} پروژه." in called_prompt
    assert "متن کاملاً بی‌ربط" not in called_prompt


@patch("backend.core.strategies.hybrid_rag.FlashRankRerank")
@patch("backend.core.strategies.hybrid_rag.Settings")
def test_hybrid_rag_expanded_candidate_pool(
    mock_settings: MagicMock, mock_rerank_cls: MagicMock
) -> None:
    """Verifies that Hybrid RAG fetches an expanded candidate pool (e.g. 30) for top_k=15."""
    from llama_index.core.schema import NodeWithScore, TextNode

    mock_repo = MagicMock()
    # Mock returning 30 candidate nodes
    mock_repo.similarity_search.return_value = [
        ExtractedNode(text=f"Candidate {i}", score=0.7) for i in range(30)
    ]

    mock_rerank = MagicMock()
    # Mock reranked top 15 nodes
    mock_rerank.postprocess_nodes.return_value = [
        NodeWithScore(node=TextNode(text=f"Reranked {i}"), score=0.9 - i * 0.01)
        for i in range(15)
    ]
    mock_rerank_cls.return_value = mock_rerank

    mock_llm = MagicMock()
    mock_llm.complete.return_value = "Aggregated Hybrid Response"
    mock_settings.llm = mock_llm

    strategy = HybridRAGStrategy(mock_repo, top_k_retrieve=25, top_n_rerank=15)
    result = strategy.execute("query", [], top_k=15)

    assert result.answer == "Aggregated Hybrid Response"
    assert len(result.source_nodes) == 15
    mock_repo.similarity_search.assert_called_with(
        "query", top_k=30, session_id=None, file_filter=None
    )


def test_strict_rag_prompt_has_persian_and_code_rules() -> None:
    """Verifies that STRICT_RAG_PROMPT_TEMPLATE enforces Persian output and code matching."""
    from backend.core.strategies.strict_rag import STRICT_RAG_PROMPT_TEMPLATE

    assert "MANDATORY LANGUAGE RULES" in STRICT_RAG_PROMPT_TEMPLATE
    assert "Always respond in Persian (فارسی)" in STRICT_RAG_PROMPT_TEMPLATE
    assert "Chinese" in STRICT_RAG_PROMPT_TEMPLATE
    assert "CONTENT & CODE VERIFICATION RULES" in STRICT_RAG_PROMPT_TEMPLATE
    assert "بله، این اطلاعات/کد در سند وجود دارد" in STRICT_RAG_PROMPT_TEMPLATE


def test_hybrid_rag_prompt_has_persian_and_code_rules() -> None:
    """Verifies that HYBRID_RAG_PROMPT_TEMPLATE enforces Persian output and code matching."""
    from backend.core.strategies.hybrid_rag import HYBRID_RAG_PROMPT_TEMPLATE

    assert "MANDATORY LANGUAGE RULES" in HYBRID_RAG_PROMPT_TEMPLATE
    assert "Always respond in Persian (فارسی)" in HYBRID_RAG_PROMPT_TEMPLATE
    assert "Chinese" in HYBRID_RAG_PROMPT_TEMPLATE
    assert "CONTENT & CODE VERIFICATION RULES" in HYBRID_RAG_PROMPT_TEMPLATE


def test_condenser_prompt_has_code_preservation_rule() -> None:
    """Verifies that CONDENSE_PROMPT_TEMPLATE instructs preserving code snippets verbatim."""
    from backend.core.condenser import CONDENSE_PROMPT_TEMPLATE

    assert (
        "CRITICAL INSTRUCTION FOR CODE & TECHNICAL QUERIES" in CONDENSE_PROMPT_TEMPLATE
    )
    assert "DO NOT alter, translate, or remove the code" in CONDENSE_PROMPT_TEMPLATE
