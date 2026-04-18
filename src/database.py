"""
Qdrant vector database manager.
Handles connection, collection creation, upsert, and search operations.
"""

from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from .config import settings
from .models import LegalChunk, SearchResult, SearchSource

logger = logging.getLogger(__name__)


class QdrantManager:
    """Manages all interactions with the Qdrant vector database."""

    def __init__(self) -> None:
        if settings.QDRANT_IN_MEMORY:
            logger.info("Using in-memory Qdrant (dev mode).")
            self.client = QdrantClient(":memory:")
        else:
            logger.info(
                "Connecting to Qdrant at %s:%s",
                settings.QDRANT_HOST,
                settings.QDRANT_PORT,
            )
            self.client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                timeout=60,
            )
        self.collection_name = settings.QDRANT_COLLECTION

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def create_collection(self, recreate: bool = False) -> None:
        """
        Create the Qdrant collection with vector config and payload indices.

        Args:
            recreate: If True, delete existing collection first.
        """
        exists = self.client.collection_exists(self.collection_name)

        if exists and recreate:
            logger.warning("Deleting existing collection '%s'.", self.collection_name)
            self.client.delete_collection(self.collection_name)
            exists = False

        if not exists:
            logger.info(
                "Creating collection '%s' (dim=%d, distance=Cosine).",
                self.collection_name,
                settings.EMBEDDING_DIM,
            )
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )

            # Create payload indices for fast filtering
            for field, schema_type in [
                ("document_id", PayloadSchemaType.KEYWORD),
                ("law_name", PayloadSchemaType.TEXT),
                ("article_id", PayloadSchemaType.KEYWORD),
                ("validity_status", PayloadSchemaType.KEYWORD),
                ("doc_type", PayloadSchemaType.KEYWORD),
                ("chunk_index", PayloadSchemaType.INTEGER),
            ]:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=schema_type,
                )

            logger.info("Collection '%s' created with payload indices.", self.collection_name)
        else:
            logger.info("Collection '%s' already exists.", self.collection_name)

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert_batch(
        self,
        chunks: list[LegalChunk],
        embeddings: list[list[float]],
        batch_size: int = 100,
    ) -> int:
        """
        Upsert chunks with their embedding vectors in batches.

        Returns:
            Number of points upserted.
        """
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        total = 0
        for start in range(0, len(chunks), batch_size):
            end = min(start + batch_size, len(chunks))
            points = []
            for chunk, emb in zip(chunks[start:end], embeddings[start:end]):
                point = PointStruct(
                    id=chunk.chunk_id,
                    vector=emb,
                    payload={
                        "document_id": chunk.document_id,
                        "law_name": chunk.law_name,
                        "article_id": chunk.article_id,
                        "content": chunk.content,
                        "validity_status": chunk.validity_status,
                        "doc_type": chunk.doc_type,
                        "chunk_index": chunk.chunk_index,
                    },
                )
                points.append(point)

            self.client.upsert(
                collection_name=self.collection_name,
                points=points,
            )
            total += len(points)
            logger.debug("Upserted batch %d–%d (%d points).", start, end, len(points))

        logger.info("Upserted %d points total.", total)
        return total

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search_dense(
        self,
        query_vector: list[float],
        top_k: int = 10,
        validity_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Dense vector search with optional validity filter.
        Gracefully handles missing collection.
        """
        if not self.client.collection_exists(self.collection_name):
            logger.warning("Collection %s does not exist yet. Returning empty.", self.collection_name)
            return []

        search_filter = None
        if validity_filter:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="validity_status",
                        match=MatchValue(value=validity_filter),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=search_filter,
            with_payload=True,
        )

        results = []
        for hit in response.points:
            payload = hit.payload or {}
            chunk = LegalChunk(
                chunk_id=str(hit.id),
                document_id=payload.get("document_id", ""),
                law_name=payload.get("law_name", ""),
                article_id=payload.get("article_id", ""),
                content=payload.get("content", ""),
                validity_status=payload.get("validity_status", ""),
                doc_type=payload.get("doc_type", ""),
                chunk_index=payload.get("chunk_index", 0),
            )
            results.append(SearchResult(chunk=chunk, score=hit.score, source=SearchSource.DENSE))

        return results

    # ------------------------------------------------------------------
    # Fetch by IDs (for context injection)
    # ------------------------------------------------------------------

    def get_by_ids(self, chunk_ids: list[str]) -> list[LegalChunk]:
        """Retrieve specific chunks by their IDs."""
        if not chunk_ids:
            return []

        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=chunk_ids,
            with_payload=True,
        )

        chunks = []
        for pt in points:
            payload = pt.payload or {}
            chunks.append(
                LegalChunk(
                    chunk_id=str(pt.id),
                    document_id=payload.get("document_id", ""),
                    law_name=payload.get("law_name", ""),
                    article_id=payload.get("article_id", ""),
                    content=payload.get("content", ""),
                    validity_status=payload.get("validity_status", ""),
                    doc_type=payload.get("doc_type", ""),
                    chunk_index=payload.get("chunk_index", 0),
                )
            )
        return chunks

    # ------------------------------------------------------------------
    # Fetch adjacent chunks (context window)
    # ------------------------------------------------------------------

    def get_adjacent_chunks(
        self,
        document_id: str,
        chunk_index: int,
        window: int = 1,
    ) -> list[LegalChunk]:
        """
        Fetch chunks adjacent to the given chunk_index for context injection.
        Retrieves chunks with chunk_index in [chunk_index-window, chunk_index+window].
        """
        results = []
        for offset in range(-window, window + 1):
            if offset == 0:
                continue
            target_index = chunk_index + offset
            if target_index < 0:
                continue

            hits = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                        FieldCondition(key="chunk_index", match=MatchValue(value=target_index)),
                    ]
                ),
                limit=1,
                with_payload=True,
            )

            points, _ = hits
            for pt in points:
                payload = pt.payload or {}
                results.append(
                    LegalChunk(
                        chunk_id=str(pt.id),
                        document_id=payload.get("document_id", ""),
                        law_name=payload.get("law_name", ""),
                        article_id=payload.get("article_id", ""),
                        content=payload.get("content", ""),
                        validity_status=payload.get("validity_status", ""),
                        doc_type=payload.get("doc_type", ""),
                        chunk_index=payload.get("chunk_index", 0),
                    )
                )

        return results

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def get_collection_info(self) -> dict:
        """Return collection stats."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "points_count": info.points_count,
                "vectors_count": info.vectors_count,
                "status": info.status.value if info.status else "unknown",
            }
        except Exception as e:
            return {"name": self.collection_name, "error": str(e)}
