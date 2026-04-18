"""
BM25 sparse index for Vietnamese legal documents.
Wraps rank_bm25.BM25Okapi with persistence and Vietnamese tokenisation.
"""

from __future__ import annotations

import logging
import os
import pickle
from typing import Optional

from rank_bm25 import BM25Okapi

from .text_processing import tokenize_vietnamese

logger = logging.getLogger(__name__)


class BM25Index:
    """
    Persistent BM25 index for sparse retrieval.

    Usage:
        idx = BM25Index()
        idx.build(documents=["doc text 1", "doc text 2", ...],
                  doc_ids=["id1", "id2", ...])
        results = idx.search("query text", top_k=10)
        idx.save("data/bm25_index.pkl")

        # Later …
        idx2 = BM25Index.load("data/bm25_index.pkl")
    """

    def __init__(self) -> None:
        self._bm25: Optional[BM25Okapi] = None
        self._doc_ids: list[str] = []
        self._corpus_tokens: list[list[str]] = []

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self, documents: list[str], doc_ids: list[str]) -> None:
        """
        Build the BM25 index from raw document texts.

        Args:
            documents: List of document / chunk texts.
            doc_ids:   Corresponding unique IDs (same length as documents).
        """
        if len(documents) != len(doc_ids):
            raise ValueError("documents and doc_ids must have the same length")

        logger.info("Tokenising %d documents for BM25 …", len(documents))
        self._corpus_tokens = [tokenize_vietnamese(doc) for doc in documents]
        self._doc_ids = list(doc_ids)

        logger.info("Building BM25Okapi index …")
        self._bm25 = BM25Okapi(self._corpus_tokens)
        logger.info("BM25 index built (%d documents).", len(self._doc_ids))

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """
        Search the BM25 index.

        Args:
            query: Raw query string (will be tokenised).
            top_k: Number of top results.

        Returns:
            List of (doc_id, bm25_score) tuples, sorted by score descending.
        """
        if self._bm25 is None:
            raise RuntimeError("BM25 index not built. Call build() or load() first.")

        tokens = tokenize_vietnamese(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)

        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        return [(self._doc_ids[i], float(scores[i])) for i in top_indices]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        """Save the index to disk via pickle."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = {
            "corpus_tokens": self._corpus_tokens,
            "doc_ids": self._doc_ids,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)
        logger.info("BM25 index saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "BM25Index":
        """Load a persisted index from disk."""
        with open(path, "rb") as f:
            data = pickle.load(f)

        idx = cls()
        idx._corpus_tokens = data["corpus_tokens"]
        idx._doc_ids = data["doc_ids"]
        idx._bm25 = BM25Okapi(idx._corpus_tokens)
        logger.info("BM25 index loaded from %s (%d docs)", path, len(idx._doc_ids))
        return idx

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._doc_ids)

    @property
    def is_built(self) -> bool:
        return self._bm25 is not None
