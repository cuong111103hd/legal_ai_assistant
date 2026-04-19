"""
Hybrid retriever: Dense (Qdrant) + Sparse (BM25) + Reciprocal Rank Fusion.
Includes context injection for surrounding articles.
"""

from __future__ import annotations

import logging
import os
import pickle
from typing import Optional
from langsmith import traceable

from sentence_transformers import SentenceTransformer

from .config import settings
from .database import QdrantManager
from .models import (
    Citation,
    EvidencePack,
    LegalChunk,
    SearchResult,
    SearchSource,
)
from .utils.bm25_index import BM25Index
from .utils.text_processing import (
    extract_article_id,
    extract_clause_id,
    extract_document_number,
    normalize_vietnamese,
)

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Combines dense vector search (Qdrant) and sparse BM25 search
    with Reciprocal Rank Fusion (RRF) for robust retrieval.
    """

    def __init__(self) -> None:
        logger.info("Initialising HybridRetriever …")

        # Dense components
        self._embed_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self._db = QdrantManager()

        # Sparse component
        self._bm25: Optional[BM25Index] = None
        self._chunk_lookup: dict[str, dict] = {}
        self._load_bm25()

        logger.info("HybridRetriever ready.")

    # ------------------------------------------------------------------
    # Internal loaders
    # ------------------------------------------------------------------

    def _load_bm25(self) -> None:
        """Load BM25 index and chunk metadata from disk if available."""
        if os.path.exists(settings.BM25_INDEX_PATH):
            try:
                self._bm25 = BM25Index.load(settings.BM25_INDEX_PATH)
            except Exception as e:
                logger.warning("Failed to load BM25 index: %s", e)
                self._bm25 = None

        if os.path.exists(settings.CHUNKS_METADATA_PATH):
            try:
                with open(settings.CHUNKS_METADATA_PATH, "rb") as f:
                    self._chunk_lookup = pickle.load(f)
                logger.info("Loaded %d chunk metadata entries.", len(self._chunk_lookup))
            except Exception as e:
                logger.warning("Failed to load chunk metadata: %s", e)

    def reload_indices(self) -> None:
        """Reload BM25 and chunk metadata (called after ingestion)."""
        self._load_bm25()

    # ------------------------------------------------------------------
    # Encode query
    # ------------------------------------------------------------------

    def _encode_query(self, query: str) -> list[float]:
        """Encode a query string into a dense vector."""
        query = normalize_vietnamese(query)
        emb = self._embed_model.encode(
            query,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return emb.tolist()

    # ------------------------------------------------------------------
    # Dense search
    # ------------------------------------------------------------------

    @traceable(name="Dense Search (Qdrant)")
    def search_dense(
        self,
        query: str,
        top_k: int = 10,
        validity_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """Run dense vector search on Qdrant."""
        vector = self._encode_query(query)
        return self._db.search_dense(vector, top_k=top_k, validity_filter=validity_filter)

    # ------------------------------------------------------------------
    # Sparse (BM25) search
    # ------------------------------------------------------------------

    @traceable(name="Sparse Search (BM25)")
    def search_sparse(self, query: str, top_k: int = 10) -> list[SearchResult]:
        """Run BM25 sparse search."""
        if not self._bm25 or not self._bm25.is_built:
            logger.warning("BM25 index not available. Returning empty results.")
            return []

        hits = self._bm25.search(query, top_k=top_k)
        results: list[SearchResult] = []

        for chunk_id, score in hits:
            meta = self._chunk_lookup.get(chunk_id)
            if meta:
                chunk = LegalChunk(**meta)
            else:
                chunk = LegalChunk(chunk_id=chunk_id, document_id="", content="")

            results.append(SearchResult(chunk=chunk, score=score, source=SearchSource.SPARSE))

        return results

    # ------------------------------------------------------------------
    # Reciprocal Rank Fusion (RRF)
    # ------------------------------------------------------------------

    @staticmethod
    def _reciprocal_rank_fusion(
        result_lists: list[list[SearchResult]],
        k: int = 60,
    ) -> list[SearchResult]:
        """
        Merge multiple ranked lists using RRF.

        RRF_score(d) = Σ  1 / (k + rank_i(d))

        Args:
            result_lists: List of ranked SearchResult lists.
            k: RRF constant (default 60).

        Returns:
            Merged list sorted by fused RRF score descending.
        """
        scores: dict[str, float] = {}
        chunk_map: dict[str, LegalChunk] = {}

        for results in result_lists:
            for rank, sr in enumerate(results, start=1):
                cid = sr.chunk.chunk_id
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
                if cid not in chunk_map:
                    chunk_map[cid] = sr.chunk

        fused = [
            SearchResult(chunk=chunk_map[cid], score=score, source=SearchSource.HYBRID)
            for cid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
        ]

        return fused

    # ------------------------------------------------------------------
    # Context injection
    # ------------------------------------------------------------------

    def _inject_context(self, results: list[SearchResult]) -> list[SearchResult]:
        """
        For each top result, fetch parent/sibling chunks to maintain
        full legal context (surrounding Điều).
        """
        window = settings.CONTEXT_WINDOW
        if window <= 0:
            return results

        seen_ids = {sr.chunk.chunk_id for sr in results}
        extra_chunks: list[SearchResult] = []

        for sr in results:
            adjacent = self._db.get_adjacent_chunks(
                document_id=sr.chunk.document_id,
                chunk_index=sr.chunk.chunk_index,
                window=window,
            )
            for adj in adjacent:
                if adj.chunk_id not in seen_ids:
                    seen_ids.add(adj.chunk_id)
                    extra_chunks.append(
                        SearchResult(chunk=adj, score=0.0, source=SearchSource.HYBRID)
                    )

        # Append context chunks after the main results
        return results + extra_chunks

    # ------------------------------------------------------------------
    # Main hybrid search
    # ------------------------------------------------------------------

    @traceable(name="Hybrid Retrieval Pipeline")
    def search(
        self,
        query: str,
        top_k: int | None = None,
        validity_filter: Optional[str] = None,
        inject_context: bool = True,
    ) -> list[SearchResult]:
        """
        Full hybrid search pipeline:
          1. Dense search (Qdrant)
          2. Sparse search (BM25)
          3. RRF fusion
          4. Context injection

        Args:
            query: User's legal question.
            top_k: Number of results (defaults to settings.TOP_K).
            validity_filter: Optional filter on validity_status.
            inject_context: Whether to fetch adjacent chunks.

        Returns:
            List of SearchResult sorted by relevance.
        """
        top_k = top_k or settings.TOP_K

        logger.info("Hybrid search: '%s' (top_k=%d)", query[:80], top_k)

        # 1. Dense search
        dense_results = self.search_dense(query, top_k=top_k, validity_filter=validity_filter)
        logger.info("Dense search returned %d results.", len(dense_results))

        # 2. Sparse search
        sparse_results = self.search_sparse(query, top_k=top_k)
        logger.info("Sparse search returned %d results.", len(sparse_results))

        # 3. RRF fusion
        fused = self._reciprocal_rank_fusion(
            [dense_results, sparse_results],
            k=settings.RRF_K,
        )

        # Take top_k after fusion
        fused = fused[:top_k]
        logger.info("RRF produced %d fused results.", len(fused))

        # 4. Context injection
        if inject_context:
            fused = self._inject_context(fused)
            logger.info("After context injection: %d total results.", len(fused))

        return fused

    # ------------------------------------------------------------------
    # Build EvidencePack from search results
    # ------------------------------------------------------------------

    @staticmethod
    def build_evidence_pack(results: list[SearchResult]) -> EvidencePack:
        """
        Convert search results into a structured EvidencePack for the LLM.
        """
        citations: list[Citation] = []
        seen: set[str] = set()

        for sr in results:
            chunk = sr.chunk
            article = chunk.article_id or extract_article_id(chunk.content)
            clause = extract_clause_id(chunk.content)
            doc_num = extract_document_number(chunk.law_name) or extract_document_number(chunk.content)

            # Deduplicate by article + law_name
            key = f"{article}|{chunk.law_name}"
            if key in seen:
                continue
            seen.add(key)

            # Use first ~500 chars as excerpt
            excerpt = chunk.content[:500].strip()
            if len(chunk.content) > 500:
                excerpt += " …"

            citations.append(
                Citation(
                    article=article or "N/A",
                    clause=clause,
                    law_name=chunk.law_name,
                    document_number=doc_num,
                    document_id=chunk.document_id,
                    excerpt=excerpt,
                )
            )

        return EvidencePack(citations=citations)



# if __name__ == "__main__":
#     retriever = HybridRetriever()
#     results = retriever.search("Hợp đồng lao dộng không có bảo hiểm có vi phạm pháp luật không")
#     for result in results:
#         print(result.chunk.content)
#         print("-" * 80)