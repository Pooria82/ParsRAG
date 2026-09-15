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
    mock_repo.similarity_search.assert_called_once()
    mock_rerank.postprocess_nodes.assert_called_once()
    mock_llm.complete.assert_called_once()
