from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.postprocessor.flashrank_rerank import FlashRankRerank  # type: ignore

from backend.core.models.domain import QueryResponse
from backend.core.strategies.base_strategy import RAGStrategy
from backend.infrastructure.database.qdrant_repo import QdrantRepository

HYBRID_RAG_PROMPT_TEMPLATE = """\
You are an intelligent AI assistant. Use the following context to answer the user's question.
If the context is somewhat relevant, provide the best answer you can, integrating your own knowledge if necessary.

Context:
{context_str}

Query: {query}
Answer:"""


class HybridRAGStrategy(RAGStrategy):
    """Executes a hybrid RAG strategy with fallback.

    This strategy attempts to retrieve and rerank relevant context to answer
    the query. If no relevant context is found, it falls back to the LLM's
    internal knowledge.
    """

    def __init__(
        self,
        collection_name: str = "parsrag_docs",
        top_k_retrieve: int = 10,
        top_n_rerank: int = 3,
    ):
        self.repo = QdrantRepository(collection_name=collection_name)
        self.prompt_template = PromptTemplate(HYBRID_RAG_PROMPT_TEMPLATE)
        self.llm = Settings.llm
        self.top_k_retrieve = top_k_retrieve
        self.reranker = FlashRankRerank(top_n=top_n_rerank)

    def execute(
        self,
        query: str,
        chat_history: list[ChatMessage],
        session_id: str | None = None,
    ) -> QueryResponse:
        """Executes the hybrid RAG pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.

        Returns:
            QueryResponse: The generated answer from context or fallback.
        """
        # 1. Retrieve (broad fetch)
        extracted_nodes = self.repo.similarity_search(
            query, top_k=self.top_k_retrieve, session_id=session_id
        )

        if not extracted_nodes:
            return QueryResponse(answer="هیچ سند مرتبطی یافت نشد. (No relevant documents found.)")

        # 2. Map to LlamaIndex Node structures for reranking
        nodes_with_score = [
            NodeWithScore(
                node=TextNode(text=n.text, metadata=n.metadata), score=n.score or 0.0
            )
            for n in extracted_nodes
        ]

        # 3. Rerank
        query_bundle = QueryBundle(query_str=query)
        reranked_nodes = self.reranker.postprocess_nodes(
            nodes_with_score, query_bundle=query_bundle
        )

        # 4. Synthesize
        context_str = "\n\n".join([n.get_content() for n in reranked_nodes])
        prompt = self.prompt_template.format(context_str=context_str, query=query)

        response = self.llm.complete(prompt)
        return QueryResponse(answer=str(response).strip())
