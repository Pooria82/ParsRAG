import hashlib
import os
import uuid
from typing import cast

from llama_index.core import Settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.core.exceptions import VectorDBConnectionError
from backend.core.interfaces.repository import AbstractDocumentRepository
from backend.core.models.domain import ExtractedNode


class QdrantRepository(AbstractDocumentRepository):
    """Qdrant-backed implementation of the Document Repository.

    Handles creation of collections, generating embeddings for documents,
    storing nodes, and performing cosine similarity searches.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str | None = None,
        vector_size: int | None = None,
    ) -> None:
        """Connect to Qdrant and validate the embedding-specific collection."""
        if host == ":memory:":
            self.client = QdrantClient(location=":memory:")
        else:
            self.client = QdrantClient(host=host, port=port)
        self.vector_size = vector_size or self._embedding_dimension()
        self.collection_name = collection_name or self._versioned_collection_name()
        self._ensure_collection_and_indices()

    def _embedding_dimension(self) -> int:
        """Derive vector dimensions from the configured embedding adapter."""
        embedding = Settings.embed_model.get_text_embedding("dimension probe")
        if not embedding:
            raise VectorDBConnectionError(
                "The embedding model returned an empty vector."
            )
        return len(embedding)

    def _versioned_collection_name(self) -> str:
        """Keep incompatible embedding schemas in separate collections."""
        explicit = os.getenv("QDRANT_COLLECTION", "").strip()
        if explicit:
            return explicit
        model_name = os.getenv("EMBED_MODEL_NAME", "intfloat/multilingual-e5-base")
        version = hashlib.sha256(model_name.encode("utf-8")).hexdigest()[:12]
        return f"parsrag_{version}"

    def _existing_vector_size(self) -> int | None:
        """Read the vector size advertised by an existing collection."""
        info = self.client.get_collection(self.collection_name)
        vectors = info.config.params.vectors
        if isinstance(vectors, qmodels.VectorParams):
            return vectors.size
        if isinstance(vectors, dict) and len(vectors) == 1:
            candidate = next(iter(vectors.values()))
            return (
                candidate.size if isinstance(candidate, qmodels.VectorParams) else None
            )
        return None

    def _ensure_collection_and_indices(self) -> None:
        try:
            exists = self.client.collection_exists(self.collection_name)
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=self.vector_size,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
            else:
                stored_size = self._existing_vector_size()
                if stored_size is not None and stored_size != self.vector_size:
                    raise VectorDBConnectionError(
                        "The Qdrant collection embedding dimension does not match "
                        f"the active model ({stored_size} != {self.vector_size})."
                    )
            # Ensure payload indices on session_id and filename
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="session_id",
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="filename",
                field_schema=qmodels.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:
            # If payload indices already exist or connection succeeds, ignore index re-creation errors
            if "already exists" not in str(exc).lower():
                raise VectorDBConnectionError(
                    f"Failed to connect to or initialize Qdrant collection: {exc}"
                ) from exc

    def is_ready(self) -> bool:
        """Return whether Qdrant can read the active collection metadata."""
        try:
            return bool(self.client.collection_exists(self.collection_name))
        except Exception:  # noqa: BLE001 - readiness must collapse adapter failures.
            return False

    def save_nodes(self, nodes: list[ExtractedNode], session_id: str) -> None:
        """Saves a list of ExtractedNode objects into Qdrant.

        Args:
            nodes (list[ExtractedNode]): The document chunks to save.
            session_id: Required session ID for filtering context.
        """
        if not nodes:
            return

        try:
            texts = [node.text for node in nodes]
            embeddings = Settings.embed_model.get_text_embedding_batch(texts)

            points = []
            for node, emb in zip(nodes, embeddings, strict=True):
                payload = node.metadata.copy()
                payload["text"] = node.text
                payload["session_id"] = session_id

                points.append(
                    qmodels.PointStruct(
                        id=str(uuid.uuid4()), vector=emb, payload=payload
                    )
                )

            # Batched upserts for high throughput
            self.client.upsert(collection_name=self.collection_name, points=points)
        except Exception as exc:
            raise VectorDBConnectionError(
                f"Failed to save nodes in Qdrant: {exc}"
            ) from exc

    def similarity_search(
        self,
        query: str,
        top_k: int = 15,
        session_id: str | None = None,
        file_filter: list[str] | None = None,
    ) -> list[ExtractedNode]:
        """Searches for the most similar nodes to the given query.

        Args:
            query (str): The search text.
            top_k (int, optional): Number of results to return. Defaults to 15.
            session_id (str | None, optional): The session ID to restrict search.
            file_filter (list[str] | None, optional): Optional list of filenames to filter by.

        Returns:
            list[ExtractedNode]: The retrieved document nodes.
        """
        if file_filter == []:
            return []
        try:
            query_embedding = Settings.embed_model.get_text_embedding(query)

            if session_id is None:
                return []

            must_conditions: list[qmodels.Condition] = [
                qmodels.FieldCondition(
                    key="session_id", match=qmodels.MatchValue(value=session_id)
                )
            ]

            # Filter by filename(s) if provided
            if file_filter:
                file_conditions: list[qmodels.Condition] = [
                    qmodels.FieldCondition(
                        key="filename", match=qmodels.MatchValue(value=fn)
                    )
                    for fn in file_filter
                ]
                must_conditions.append(qmodels.Filter(should=file_conditions))

            filter_query = qmodels.Filter(must=must_conditions)

            search_result = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=filter_query,
                limit=top_k,
            ).points

            extracted_nodes = []
            for hit in search_result:
                payload = hit.payload or {}
                text = payload.pop("text", "")
                payload.pop("session_id", None)
                extracted_nodes.append(
                    ExtractedNode(text=text, metadata=payload, score=hit.score)
                )

            return extracted_nodes
        except Exception as exc:
            raise VectorDBConnectionError(
                f"Failed to perform similarity search in Qdrant: {exc}"
            ) from exc

    def get_session_files(self, session_id: str) -> list[str]:
        """Returns the list of distinct filenames indexed in the given session.

        Args:
            session_id (str): The session ID to inspect.

        Returns:
            list[str]: Distinct filenames in the session.
        """
        try:
            scroll_filter = qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="session_id", match=qmodels.MatchValue(value=session_id)
                    )
                ]
            )
            filenames: set[str] = set()
            offset: int | str | uuid.UUID | None = None
            while True:
                results, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=scroll_filter,
                    limit=256,
                    offset=offset,
                    with_payload=["filename"],
                    with_vectors=False,
                )
                for point in results:
                    if point.payload and "filename" in point.payload:
                        filenames.add(str(point.payload["filename"]))
                if next_offset is None:
                    break
                offset = cast(int | str | uuid.UUID, next_offset)
            return sorted(filenames)
        except Exception as exc:
            raise VectorDBConnectionError(
                f"Failed to retrieve session files in Qdrant: {exc}"
            ) from exc

    def delete_session(self, session_id: str) -> None:
        """Deletes all nodes associated with a specific session ID.

        Args:
            session_id (str): The session ID to delete.
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="session_id",
                                match=qmodels.MatchValue(value=session_id),
                            )
                        ]
                    )
                ),
            )
        except Exception as exc:
            raise VectorDBConnectionError(
                f"Failed to delete session nodes in Qdrant: {exc}"
            ) from exc

    def delete_document(self, session_id: str, filename: str) -> None:
        """Deletes every chunk for one document in a session."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(
                        must=[
                            qmodels.FieldCondition(
                                key="session_id",
                                match=qmodels.MatchValue(value=session_id),
                            ),
                            qmodels.FieldCondition(
                                key="filename", match=qmodels.MatchValue(value=filename)
                            ),
                        ]
                    )
                ),
            )
        except Exception as exc:
            raise VectorDBConnectionError(
                f"Failed to delete document nodes in Qdrant: {exc}"
            ) from exc
