import uuid
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from llama_index.core import Settings
from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import ExtractedNode

class QdrantRepository(AbstractDocumentRepository):
    def __init__(self, host: str = "localhost", port: int = 6333, collection_name: str = "parsrag_collection"):
        self.client = QdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self._ensure_collection_and_indices()

    def _ensure_collection_and_indices(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=qmodels.VectorParams(
                    size=768, # e5-base dimensions
                    distance=qmodels.Distance.COSINE
                )
            )
            # Ensure payload index on session_id for optimized filtering
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="session_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD
            )

    def save_nodes(self, nodes: List[ExtractedNode], session_id: Optional[str] = None) -> None:
        if not nodes:
            return
        
        texts = [node.text for node in nodes]
        embeddings = Settings.embed_model.get_text_embedding_batch(texts)
        
        points = []
        for idx, (node, emb) in enumerate(zip(nodes, embeddings)):
            payload = node.metadata.copy()
            payload["text"] = node.text
            payload["session_id"] = session_id or "global"
            
            points.append(
                qmodels.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=emb,
                    payload=payload
                )
            )
        
        # Batched upserts for high throughput
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

    def similarity_search(self, query: str, top_k: int = 5, session_id: Optional[str] = None) -> List[ExtractedNode]:
        query_embedding = Settings.embed_model.get_text_embedding(query)
        
        # Filter by session_id OR global
        should_conditions = [
            qmodels.FieldCondition(
                key="session_id",
                match=qmodels.MatchValue(value="global")
            )
        ]
        if session_id:
            should_conditions.append(
                qmodels.FieldCondition(
                    key="session_id",
                    match=qmodels.MatchValue(value=session_id)
                )
            )
            
        filter_query = qmodels.Filter(should=should_conditions)
        
        search_result = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=filter_query,
            limit=top_k
        )
        
        extracted_nodes = []
        for hit in search_result:
            payload = hit.payload or {}
            text = payload.pop("text", "")
            payload.pop("session_id", None)
            extracted_nodes.append(
                ExtractedNode(
                    text=text,
                    metadata=payload,
                    score=hit.score
                )
            )
            
        return extracted_nodes

    def delete_session(self, session_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="session_id",
                            match=qmodels.MatchValue(value=session_id)
                        )
                    ]
                )
            )
        )
