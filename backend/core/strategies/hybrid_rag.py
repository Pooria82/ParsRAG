import os

from llama_index.core import Settings
from llama_index.core.llms import ChatMessage
from llama_index.core.prompts import PromptTemplate
from llama_index.core.schema import NodeWithScore, QueryBundle, TextNode
from llama_index.postprocessor.flashrank_rerank import FlashRankRerank  # type: ignore

from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import ExtractedNode, QueryResponse
from backend.core.strategies.base_strategy import RAGStrategy

HYBRID_RAG_PROMPT_TEMPLATE = """\
You are an intelligent AI assistant. Use the following context to answer the user's question.
If the context contains relevant information, synthesize the answer comprehensively using all relevant details from the provided sections. If needed, you may integrate your own knowledge to complement the context.

Context:
{context_str}

Query: {query}
Answer:"""


class HybridRAGStrategy(RAGStrategy):
    """Executes a hybrid RAG strategy with fallback and reranking.

    This strategy retrieves a broad candidate pool across the document collection,
    reranks them using FlashRank to extract the most relevant chunks, and synthesizes
    the answer.
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
    ) -> QueryResponse:
        """Executes the hybrid RAG pipeline.

        Args:
            query (str): The user's input query.
            chat_history (list[ChatMessage]): Previous chat context.
            session_id (str | None, optional): The session ID for context filtering.
            top_k (int | None, optional): Optional override for number of reranked chunks.

        Returns:
            QueryResponse: The generated answer and source citations.
        """
        # 1. Determine retrieval and reranking depths
        rerank_n = top_k if top_k is not None else self.default_rerank_n
        retrieve_k = max(rerank_n * 2, self.default_retrieve_k)

        # 2. Broad Candidate Retrieval
        extracted_nodes = self.repo.similarity_search(
            query, top_k=retrieve_k, session_id=session_id
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

        # 5. Build context with source nodes
        final_source_nodes: list[ExtractedNode] = []
        context_parts: list[str] = []

        for i, n in enumerate(reranked_nodes, start=1):
            text = n.get_content()
            metadata = n.node.metadata if hasattr(n.node, "metadata") else {}
            score = n.score
            final_source_nodes.append(
                ExtractedNode(text=text, metadata=metadata, score=score)
            )
            source_tag = (
                f" [سند: {metadata.get('filename', '')}]"
                if metadata.get("filename")
                else ""
            )
            context_parts.append(f"--- بخش {i}{source_tag} ---\n{text}")

        context_str = "\n\n".join(context_parts)
        prompt = self.prompt_template.format(context_str=context_str, query=query)

        response = self.llm.complete(prompt)
        return QueryResponse(
            answer=str(response).strip(),
            source_nodes=final_source_nodes,
        )
