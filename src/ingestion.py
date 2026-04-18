"""
Data ingestion pipeline.
Loads the HuggingFace dataset, chunks legal documents, generates embeddings,
and upserts into Qdrant + builds the BM25 index.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional
from uuid import uuid4

from datasets import load_dataset
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from .config import settings
from .database import QdrantManager
from .database_sql import init_db, upsert_legal_documents_batch
from .models import IngestState, IngestStatus, LegalChunk
from .utils.bm25_index import BM25Index
from .utils.text_processing import (
    clean_html,
    extract_article_id,
    extract_document_number,
    normalize_vietnamese,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level ingestion status (shared with the API layer)
# ---------------------------------------------------------------------------
_ingest_status = IngestStatus()


def get_ingest_status() -> IngestStatus:
    """Return current ingestion status (used by API)."""
    return _ingest_status


# ---------------------------------------------------------------------------
# Vietnamese-aware text splitter
# ---------------------------------------------------------------------------

def _create_legal_splitter() -> RecursiveCharacterTextSplitter:
    """
    Build a RecursiveCharacterTextSplitter optimised for Vietnamese legal
    document structure.  Splits by Điều → Khoản → Điểm → paragraph → sentence.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=[
            "\nĐiều ",       # Article boundary (highest priority)
            "\nKhoản ",      # Clause boundary
            "\nĐiểm ",      # Sub-clause boundary
            "\nMục ",        # Section
            "\nChương ",     # Chapter
            "\n\n",          # Double newline (paragraph)
            "\n",            # Single newline
            ". ",            # Sentence end
            " ",             # Word
        ],
        keep_separator=True,
        strip_whitespace=True,
    )


# ---------------------------------------------------------------------------
# Load & merge dataset
# ---------------------------------------------------------------------------

def _load_dataset(limit: Optional[int] = None):
    """
    Load metadata + content from HuggingFace OR local parquet files.
    Prioritises local files if they exist in data/raw/.
    """
    LOCAL_META = "data/raw/data/metadata.parquet"
    LOCAL_CONTENT = "data/raw/data/content.parquet"

    # 1. Try local load first
    if os.path.exists(LOCAL_META) and os.path.exists(LOCAL_CONTENT):
        import pandas as pd
        logger.info("Found local data files. Loading from disk...")
        
        meta_df = pd.read_parquet(LOCAL_META)
        content_df = pd.read_parquet(LOCAL_CONTENT)
        
        # Ensure 'id' is string in both to avoid merge errors
        meta_df["id"] = meta_df["id"].astype(str)
        content_df["id"] = content_df["id"].astype(str)
        
        # Merge on 'id'
        df = pd.merge(content_df, meta_df, on="id", how="left")
        
        if limit:
            df = df.head(limit)
            
        merged = []
        for _, row in df.iterrows():
            merged.append({
                "id": str(row.get("id", "")),
                "title": row.get("title", ""),
                "content_html": row.get("content_html", ""),
                "doc_type": row.get("loai_van_ban", ""),
                "validity_status": row.get("tinh_trang_hieu_luc", "Còn hiệu lực"),
                "document_number": row.get("so_ky_hieu", ""),
            })
        
        logger.info("Loaded %d documents from local files.", len(merged))
        return merged

    # 2. Fallback to streaming if no local files
    from datasets import Features, Value

    # Explicit features to handle LargeString and match dataset schema
    content_features = Features({
        "id": Value("large_string"),
        "content_html": Value("large_string")
    })
    
    logger.info("Local files not found. Streaming from HuggingFace …")
    meta_ds = load_dataset(settings.DATASET_NAME, "metadata", split="data", streaming=True)
    content_ds = load_dataset(settings.DATASET_NAME, "content", split="data", streaming=True, features=content_features)

    # Build lookup for metadata
    meta_lookup: dict[str, dict] = {}
    total_meta = 0
    logger.info("Iterating metadata stream...")
    for row in meta_ds:
        doc_id = str(row.get("id", ""))
        if doc_id:
            meta_lookup[doc_id] = dict(row)
            total_meta += 1
        
        if limit and total_meta > (limit * 100): # heuristic
             break
    
    logger.info("Buffered metadata for %d documents.", len(meta_lookup))

    # Merge content with metadata
    merged: list[dict] = []
    count = 0
    for row in content_ds:
        doc_id = str(row.get("id", ""))
        meta = meta_lookup.get(doc_id, {})
        merged.append({
            "id": doc_id,
            "title": meta.get("title", ""),
            "content_html": row.get("content_html", ""),
            "doc_type": meta.get("loai_van_ban", ""),
            "validity_status": meta.get("tinh_trang_hieu_luc", "Còn hiệu lực"),
            "document_number": meta.get("so_ky_hieu", ""),
        })
        count += 1
        if limit and count >= limit:
            break

    logger.info("Loaded %d documents from merged stream.", len(merged))
    return merged


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_documents(documents: list[dict]) -> list[LegalChunk]:
    """
    Split each document into LegalChunks with metadata.
    """
    splitter = _create_legal_splitter()
    all_chunks: list[LegalChunk] = []

    for doc in tqdm(documents, desc="Chunking documents"):
        text = clean_html(doc["content_html"])
        if not text or len(text.strip()) < 20:
            _ingest_status.processed_documents += 1
            continue

        splits = splitter.split_text(text)
        law_name = normalize_vietnamese(doc.get("title", ""))
        doc_number = doc.get("document_number", "") or extract_document_number(law_name)

        for idx, chunk_text in enumerate(splits):
            article_id = extract_article_id(chunk_text)
            chunk = LegalChunk(
                chunk_id=str(uuid4()),
                document_id=doc["id"],
                law_name=law_name,
                article_id=article_id,
                content=chunk_text,
                validity_status=doc.get("validity_status", "Còn hiệu lực"),
                doc_type=doc.get("doc_type", ""),
                chunk_index=idx,
            )
            all_chunks.append(chunk)
        
        # Update progress for API
        _ingest_status.processed_documents += 1

    logger.info("Created %d chunks from %d documents.", len(all_chunks), len(documents))
    return all_chunks


# ---------------------------------------------------------------------------
# Embedding generation
# ---------------------------------------------------------------------------

def _generate_embeddings(
    chunks: list[LegalChunk],
    model: SentenceTransformer,
) -> list[list[float]]:
    """
    Generate embeddings in batches to avoid OOM.
    """
    texts = [c.content for c in chunks]
    batch_size = settings.EMBEDDING_BATCH_SIZE

    logger.info(
        "Generating embeddings for %d chunks (batch_size=%d) …",
        len(texts),
        batch_size,
    )

    all_embeddings: list[list[float]] = []

    for start in tqdm(range(0, len(texts), batch_size), desc="Embedding batches"):
        batch = texts[start : start + batch_size]
        emb = model.encode(
            batch,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        all_embeddings.extend(emb.tolist())

    logger.info("Generated %d embeddings.", len(all_embeddings))
    return all_embeddings


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------

async def run_ingestion(limit: Optional[int] = None) -> IngestStatus:
    """
    End-to-end ingestion:
      1. Load dataset from HuggingFace
      2. Save full documents to PostgreSQL
      3. Chunk documents
      4. Generate embeddings
      5. Upsert into Qdrant
      6. Build & persist BM25 index

    Args:
        limit: Optional cap on number of documents to ingest.

    Returns:
        Final IngestStatus.
    """
    global _ingest_status

    _ingest_status = IngestStatus(state=IngestState.RUNNING)

    try:
        # Step 1: Load dataset
        logger.info("=== Step 1/6: Loading dataset ===")
        documents = _load_dataset(limit=limit)
        _ingest_status.total_documents = len(documents)

        # Step 2: Save full documents to PostgreSQL
        logger.info("=== Step 2/6: Saving full documents to PostgreSQL ===")
        await _async_save_to_postgres(documents)

        # Step 3: Chunk
        logger.info("=== Step 3/6: Chunking documents ===")
        _ingest_status.processed_documents = 0 # Reset for chunking step tracker
        chunks = _chunk_documents(documents)
        _ingest_status.total_chunks = len(chunks)

        if not chunks:
            _ingest_status.state = IngestState.COMPLETED
            logger.warning("No chunks produced. Ingestion complete (empty).")
            return _ingest_status

        # Step 4: Embeddings
        logger.info("=== Step 4/6: Generating embeddings ===")
        model = SentenceTransformer(settings.EMBEDDING_MODEL)
        embeddings = _generate_embeddings(chunks, model)

        # Step 5: Qdrant upsert
        logger.info("=== Step 5/6: Upserting to Qdrant ===")
        db = QdrantManager()
        db.create_collection(recreate=True)
        db.upsert_batch(chunks, embeddings)

        # Step 6: BM25 index
        logger.info("=== Step 6/6: Building BM25 index ===")
        bm25 = BM25Index()
        bm25.build(
            documents=[c.content for c in chunks],
            doc_ids=[c.chunk_id for c in chunks],
        )
        bm25.save(settings.BM25_INDEX_PATH)

        # Also persist chunk metadata for the retriever
        _save_chunk_metadata(chunks)

        _ingest_status.state = IngestState.COMPLETED
        logger.info(
            "✅ Ingestion complete: %d documents → %d chunks.",
            len(documents),
            len(chunks),
        )

    except Exception as e:
        logger.error("❌ Ingestion failed: %s", e, exc_info=True)
        _ingest_status.state = IngestState.FAILED
        _ingest_status.error_message = str(e)

    return _ingest_status


async def _async_save_to_postgres(documents: list[dict]) -> None:
    """Save full legal documents to PostgreSQL for citation deep-linking."""
    sql_docs = []
    for doc in tqdm(documents, desc="Preparing PostgreSQL records"):
        clean_text = clean_html(doc.get("content_html", ""))
        sql_docs.append({
            "id": str(doc["id"]),
            "title": doc.get("title", ""),
            "content_html": doc.get("content_html", ""),
            "clean_text": clean_text,
            "doc_type": doc.get("doc_type", ""),
            "document_number": doc.get("document_number", ""),
            "validity_status": doc.get("validity_status", "Còn hiệu lực"),
        })

    await init_db()
    count = await upsert_legal_documents_batch(sql_docs)
    logger.info("Saved %d documents to PostgreSQL.", count)



def _save_chunk_metadata(chunks: list[LegalChunk]) -> None:
    """Persist chunk metadata to disk so the retriever can rebuild LegalChunk from BM25 hits."""
    import pickle

    path = settings.CHUNKS_METADATA_PATH
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    lookup = {c.chunk_id: c.model_dump() for c in chunks}
    with open(path, "wb") as f:
        pickle.dump(lookup, f)

    logger.info("Saved chunk metadata to %s (%d entries).", path, len(lookup))
