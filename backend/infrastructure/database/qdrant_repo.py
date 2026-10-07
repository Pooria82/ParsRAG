import hashlib
import os
import uuid
from contextlib import suppress
from typing import Any, cast

import numpy as np
from llama_index.core import Settings
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.core.domain.documents import ExtractedNode
from backend.core.domain.exceptions import VectorDBConnectionError
from backend.core.port.document_repository import DocumentRepository
from backend.infrastructure.database.keyword_index import (
    SessionCorpus,
    SessionCorpusCache,
)

# Reciprocal-rank fusion constant (Cormack et al.); 60 is the usual default.
_RRF_K = 60


def keyword_search_enabled() -> bool:
    """Fuse BM25 keyword matches with vector search unless disabled."""
    value = os.getenv("KEYWORD_SEARCH", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def fuse_rankings(
    dense: list[tuple[Any, ExtractedNode]],
    keyword: list[tuple[Any, ExtractedNode]],
    *,
    limit: int,
) -> list[ExtractedNode]:
    """Reciprocal-rank fusion of two ranked lists of (point id, node)."""
    scores: dict[Any, float] = {}
    nodes: dict[Any, ExtractedNode] = {}
    for ranking in (dense, keyword):
        for rank, (point_id, node) in enumerate(ranking):
            scores[point_id] = scores.get(point_id, 0.0) + 1 / (_RRF_K + rank + 1)
            nodes.setdefault(point_id, node)
    ordered = sorted(scores, key=lambda point_id: scores[point_id], reverse=True)
    return [nodes[point_id] for point_id in ordered[:limit]]


class QdrantRepository(DocumentRepository):
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
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="content_sha256",
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
        self._keywords.invalidate(session_id)

        try:
            try:
                configured_batch_size = int(os.getenv("QDRANT_UPSERT_BATCH_SIZE", "64"))
            except ValueError:
                configured_batch_size = 64
            batch_size = min(512, max(1, configured_batch_size))
            for offset in range(0, len(nodes), batch_size):
                batch = nodes[offset : offset + batch_size]
                embeddings = Settings.embed_model.get_text_embedding_batch(
                    [node.text for node in batch]
                )
                points = []
                for node, embedding in zip(batch, embeddings, strict=True):
                    payload = node.metadata.copy()
                    payload["text"] = node.text
                    payload["session_id"] = session_id
                    points.append(
                        qmodels.PointStruct(
                            id=str(uuid.uuid4()),
                            vector=embedding,
                            payload=payload,
                        )
                    )
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

            dense = [
                (hit.id, self._node(hit.payload or {}, hit.score))
                for hit in search_result
            ]
            if not keyword_search_enabled():
                return [node for _, node in dense]
            keyword = self._keyword_hits(
                query, query_embedding, session_id, file_filter, top_k, dense
            )
            return fuse_rankings(dense, keyword, limit=top_k)
        except Exception as exc:
            raise VectorDBConnectionError(
                f"Failed to perform similarity search in Qdrant: {exc}"
            ) from exc

    @property
    def _keywords(self) -> SessionCorpusCache:
        """Per-instance keyword index cache, created on first use."""
        cache = self.__dict__.get("_keyword_cache")
        if cache is None:
            cache = SessionCorpusCache()
            self.__dict__["_keyword_cache"] = cache
        return cast(SessionCorpusCache, cache)

    @staticmethod
    def _node(payload: dict[str, Any], score: float | None) -> ExtractedNode:
        """Turn a stored payload into a node without its session field."""
        metadata = dict(payload)
        text = str(metadata.pop("text", ""))
        metadata.pop("session_id", None)
        return ExtractedNode(text=text, metadata=metadata, score=score)

    def _keyword_hits(
        self,
        query: str,
        query_embedding: list[float],
        session_id: str,
        file_filter: list[str] | None,
        top_k: int,
        dense: list[tuple[Any, ExtractedNode]],
    ) -> list[tuple[Any, ExtractedNode]]:
        """BM25 matches, scored by cosine similarity like the vector hits.

        Keeping the cosine score means Strict mode's evidence threshold
        applies unchanged to chunks that only keyword search found.
        """
        corpus = self._keywords.get(session_id, lambda: self._load_corpus(session_id))
        allowed_files = set(file_filter) if file_filter else None
        matches = corpus.search(
            query,
            top_k,
            lambda payload: (
                allowed_files is None or payload.get("filename") in allowed_files
            ),
        )
        known = {point_id: node for point_id, node in dense}
        missing = [
            corpus.ids[index] for index, _ in matches if corpus.ids[index] not in known
        ]
        cosine = self._cosine_scores(query_embedding, missing)
        hits: list[tuple[Any, ExtractedNode]] = []
        for index, _ in matches:
            point_id = corpus.ids[index]
            node = known.get(point_id) or self._node(
                {"text": corpus.texts[index], **corpus.payloads[index]},
                cosine.get(point_id),
            )
            hits.append((point_id, node))
        return hits

    def _cosine_scores(
        self, query_embedding: list[float], point_ids: list[Any]
    ) -> dict[Any, float]:
        """Fetch stored (normalized) vectors and score them against the query."""
        if not point_ids:
            return {}
        query = np.asarray(query_embedding, dtype=np.float32)
        query /= np.linalg.norm(query) or 1.0
        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=point_ids,
            with_payload=False,
            with_vectors=True,
        )
        scores: dict[Any, float] = {}
        for point in points:
            if isinstance(point.vector, list):
                vector = np.asarray(point.vector, dtype=np.float32)
                scores[point.id] = float(
                    vector @ query / (np.linalg.norm(vector) or 1.0)
                )
        return scores

    def _load_corpus(self, session_id: str) -> SessionCorpus:
        """Read every chunk text and payload of a session (no vectors)."""
        ids: list[Any] = []
        texts: list[str] = []
        payloads: list[dict[str, Any]] = []
        offset: int | str | uuid.UUID | None = None
        session_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="session_id", match=qmodels.MatchValue(value=session_id)
                )
            ]
        )
        while True:
            points, next_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=session_filter,
                limit=512,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = dict(point.payload or {})
                ids.append(point.id)
                texts.append(str(payload.pop("text", "")))
                payload.pop("session_id", None)
                payloads.append(payload)
            if next_offset is None:
                break
            offset = cast(int | str | uuid.UUID, next_offset)
        return SessionCorpus(ids=ids, texts=texts, payloads=payloads)

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

    def find_document_by_content(
        self, session_id: str, content_sha256: str
    ) -> str | None:
        """Return the filename of a session document with the same bytes."""
        try:
            points, _ = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="session_id", match=qmodels.MatchValue(value=session_id)
                        ),
                        qmodels.FieldCondition(
                            key="content_sha256",
                            match=qmodels.MatchValue(value=content_sha256),
                        ),
                    ]
                ),
                limit=1,
                with_payload=["filename"],
                with_vectors=False,
            )
        except Exception as exc:
            raise VectorDBConnectionError(
                f"Failed to look up document content in Qdrant: {exc}"
            ) from exc
        if not points or not points[0].payload:
            return None
        filename = points[0].payload.get("filename")
        return str(filename) if filename is not None else None

    def copy_document(
        self, source_session_id: str, target_session_id: str, filename: str
    ) -> int:
        """Reuse stored vectors without reading the original file or embedding again."""
        if source_session_id == target_session_id:
            raise ValueError("Source and target sessions must differ.")
        self._keywords.invalidate(target_session_id)
        source_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="session_id", match=qmodels.MatchValue(value=source_session_id)
                ),
                qmodels.FieldCondition(
                    key="filename", match=qmodels.MatchValue(value=filename)
                ),
            ]
        )
        copied = 0
        offset: int | str | uuid.UUID | None = None
        try:
            while True:
                points, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=source_filter,
                    limit=64,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )
                if points:
                    clones = []
                    for point in points:
                        vector = point.vector
                        if vector is None:
                            raise VectorDBConnectionError(
                                "Source document has a point without a vector."
                            )
                        clones.append(
                            qmodels.PointStruct(
                                id=str(uuid.uuid4()),
                                vector=cast(qmodels.VectorStruct, vector),
                                payload={
                                    **(point.payload or {}),
                                    "session_id": target_session_id,
                                },
                            )
                        )
                    self.client.upsert(
                        collection_name=self.collection_name, points=clones, wait=True
                    )
                    copied += len(clones)
                if next_offset is None:
                    break
                offset = cast(int | str | uuid.UUID, next_offset)
            return copied
        except Exception as exc:
            with suppress(VectorDBConnectionError):
                self.delete_document(target_session_id, filename)
            raise VectorDBConnectionError(
                f"Failed to reuse document vectors: {exc}"
            ) from exc

    def delete_session(self, session_id: str) -> None:
        """Deletes all nodes associated with a specific session ID.

        Args:
            session_id (str): The session ID to delete.
        """
        self._keywords.invalidate(session_id)
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
        self._keywords.invalidate(session_id)
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
