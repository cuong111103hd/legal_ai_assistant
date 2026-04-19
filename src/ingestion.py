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
from bs4 import BeautifulSoup
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

def chunk_html_by_article(
    html_content: str, 
    document_id: str, 
    law_name: str, 
    validity_status: str = "Còn hiệu lực", 
    doc_type: str = "",
    document_number: str = "",
) -> list[LegalChunk]:
    """
    Chunks a legal document by Article (Điều).
    - Metadata (article_id) = Article title (e.g. 'Điều 1. Phạm vi điều chỉnh')
    - Content = All text blocks following the article title until the next 'Điều'.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Try to target the main content container to avoid metadata tables/footers if possible
    container = soup.find("div", {"align": "justify"}) or soup.find("td", {"colspan": "3"}) or soup
    
    chunks: list[LegalChunk] = []
    current_article_id = None # Start as None to skip intro text
    current_content = []
    
    # Pattern: 'Điều 1.', 'Điều 2a.', etc. at the start of a block
    article_pattern = re.compile(r"^\s*Điều\s+(\d+[a-z]?)\s*\.", re.IGNORECASE)

    # Standard block elements in these HTML files
    for tag in container.find_all(['p', 'h3', 'h2', 'h1', 'div']):
        # If tag has children tags (like <strong>), we want the full text
        text = tag.get_text().strip()
        if not text:
            continue
            
        # Check if this tag starts a new Article
        match = article_pattern.match(text)
        if match:
            # We found a new article boundary. Save the previous one if it exists.
            if current_article_id is not None and current_content:
                chunks.append(LegalChunk(
                    chunk_id=str(uuid4()),
                    document_id=document_id,
                    law_name=law_name,
                    article_id=current_article_id,
                    content="\n".join(current_content),
                    validity_status=validity_status,
                    doc_type=doc_type,
                    document_number=document_number,
                    chunk_index=len(chunks),
                ))
            
            # Start new capture
            current_article_id = text
            current_content = [] # Reset content. 
        elif current_article_id is not None:
            # Normal text block, only append if we have already found the first Article
            current_content.append(text)

    # Final leftover chunk
    if current_article_id is not None and current_content:
        chunks.append(LegalChunk(
            chunk_id=str(uuid4()),
            document_id=document_id,
            law_name=law_name,
            article_id=current_article_id,
            content="\n".join(current_content),
            validity_status=validity_status,
            doc_type=doc_type,
            document_number=document_number,
            chunk_index=len(chunks),
        ))
        
    return chunks


# ---------------------------------------------------------------------------
# Load & merge dataset
# ---------------------------------------------------------------------------

def _load_dataset(limit: Optional[int] = None, doc_numbers: Optional[list[str]] = None):
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
        
        # --- Apply User Requested Filters ---
        count_stage0 = len(df)
        
        # If doc_numbers is provided, we skip all other filters and only take those docs
        if doc_numbers:
            logger.info("Filtering by specific document numbers: %s", doc_numbers)
            if 'so_ky_hieu' in df.columns:
                df = df[df['so_ky_hieu'].astype(str).isin(doc_numbers)]
            logger.info("Matched %d documents by number.", len(df))
        else:
            # 1. Filter by Type
            target_types = ['Luật', 'Bộ luật']
            if 'loai_van_ban' in df.columns:
                df = df[df['loai_van_ban'].astype(str).isin(target_types)]
            count_stage1 = len(df)
            
            # 2. Filter by Validity
            if 'tinh_trang_hieu_luc' in df.columns:
                target_status = ['Còn hiệu lực', 'Hết hiệu lực một phần']
                df = df[df['tinh_trang_hieu_luc'].astype(str).isin(target_status)]
            count_stage2 = len(df)
                
            # 3. Filter by Year
            if 'ngay_ban_hanh' in df.columns:
                # Parse dates (D/M/Y format as per user SQL)
                df['dt_ban_hanh'] = pd.to_datetime(df['ngay_ban_hanh'], format='%d/%m/%Y', errors='coerce')
                df = df[df['dt_ban_hanh'].dt.year >= 2015]
            count_stage3 = len(df)

            # 4. Filter by Title keywords
            if 'title' in df.columns:
                import unicodedata
                def normalize_vn(text):
                    if not isinstance(text, str): return ""
                    return unicodedata.normalize('NFC', text)
                
                keywords = ['An toàn thông tin mạng', 'An ninh mạng']
                normalized_keywords = [normalize_vn(k) for k in keywords]
                pattern = '|'.join(normalized_keywords)
                
                # Normalize the title column for robust matching
                df['title_norm'] = df['title'].apply(normalize_vn)
                df = df[df['title_norm'].str.contains(pattern, case=False, na=False)]
                df = df.drop(columns=['title_norm'])

            logger.info(f"Ingestion Filter Report:")
            logger.info(f" - Initial: {count_stage0}")
            logger.info(f" - After Type Filter ({target_types}): {count_stage1} (Dropped {count_stage0 - count_stage1})")
            logger.info(f" - After Validity Filter: {count_stage2} (Dropped {count_stage1 - count_stage2})")
            logger.info(f" - After Year Filter (>=2015): {count_stage3} (Dropped {count_stage2 - count_stage3})")
            logger.info(f" - After Title Keywords: {len(df)} (Dropped {count_stage3 - len(df)})")

        
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
                "document_number": str(row.get("so_ky_hieu", "")),
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
            # If doc_numbers is set, only buffer metadata for those docs
            if doc_numbers:
                if str(row.get("so_ky_hieu", "")) in doc_numbers:
                    meta_lookup[doc_id] = dict(row)
                    total_meta += 1
            else:
                meta_lookup[doc_id] = dict(row)
                total_meta += 1
        
        if limit and not doc_numbers and total_meta > (limit * 100): # heuristic
             break
    
    logger.info("Buffered metadata for %d documents.", len(meta_lookup))

    # Merge content with metadata
    merged: list[dict] = []
    count = 0
    target_types = ['Luật', 'Bộ luật']
    target_status = ['Còn hiệu lực', 'Hết hiệu lực một phần']
    
    for row in content_ds:
        doc_id = str(row.get("id", ""))
        meta = meta_lookup.get(doc_id, {})
        if not meta:
            continue
            
        if doc_numbers:
            # If specifically requested, no further checks needed
            pass
        else:
            # 1. Filter by Type
            if meta.get("loai_van_ban") not in target_types:
                continue
                
            # 2. Filter by Validity
            if meta.get("tinh_trang_hieu_luc") not in target_status:
                continue
                
            # 3. Filter by Year
            try:
                date_str = meta.get("ngay_ban_hanh", "")
                if date_str:
                    year = int(date_str.split('/')[-1])
                    if year < 2015:
                        continue
            except (ValueError, IndexError):
                pass

        merged.append({
            "id": doc_id,
            "title": meta.get("title", ""),
            "content_html": row.get("content_html", ""),
            "doc_type": meta.get("loai_van_ban", ""),
            "validity_status": meta.get("tinh_trang_hieu_luc", "Còn hiệu lực"),
            "document_number": str(meta.get("so_ky_hieu", "")),
        })
        count += 1
        if limit and count >= limit:
            break

    logger.info("Loaded %d documents from merged stream.", len(merged))
    return merged


async def run_ingestion_by_numbers(doc_numbers: list[str]) -> IngestStatus:
    """
    Specific ingestion for a list of document numbers.
    Bypasses all general filters!
    """
    global _ingest_status

    _ingest_status = IngestStatus(state=IngestState.RUNNING)

    try:
        logger.info("=== Targeted Ingestion: %d documents ===", len(doc_numbers))
        
        # Step 1: Load exactly those docs
        documents = _load_dataset(doc_numbers=doc_numbers)
        _ingest_status.total_documents = len(documents)

        if not documents:
            _ingest_status.state = IngestState.FAILED
            _ingest_status.error_message = "Không tìm thấy văn bản nào với mã đã cung cấp."
            return _ingest_status

        # Step 2: Save to SQL
        await _async_save_to_postgres(documents)

        # Step 3: Chunk
        chunks = _chunk_documents(documents)
        _ingest_status.total_chunks = len(chunks)

        # Step 4: Embed
        model = SentenceTransformer(settings.EMBEDDING_MODEL)
        embeddings = _generate_embeddings(chunks, model)

        # Step 5: Qdrant (UPSERT - do NOT recreate collection here!)
        db = QdrantManager()
        # We use upsert so if document already exists, it updates; else it adds.
        db.upsert_batch(chunks, embeddings)

        # Step 6: BM25 index (Incremental update is hard, so we rebuild for simplicity 
        # or skip if only adding one. For now, rebuild to keep it working.)
        bm25 = BM25Index()
        # To truly support adding/updating, we'd need to load entire DB chunks.
        # For this targeted ingest, let's assume we want them searchable.
        # Note: This might be SLOW if DB is huge.
        # TODO: Implement incremental BM25 if needed.
        
        _ingest_status.state = IngestState.COMPLETED
        logger.info("✅ Targeted ingestion complete.")

    except Exception as e:
        logger.error("❌ Targeted ingestion failed: %s", e, exc_info=True)
        _ingest_status.state = IngestState.FAILED
        _ingest_status.error_message = str(e)

    return _ingest_status


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _chunk_documents(documents: list[dict]) -> list[LegalChunk]:
    """
    Split each document into LegalChunks with metadata.
    """
    all_chunks: list[LegalChunk] = []

    for doc in tqdm(documents, desc="Chunking documents"):
        # --- NEW Structure-aware Chunking ---
        doc_chunks = chunk_html_by_article(
            html_content=doc["content_html"],
            document_id=doc["id"],
            law_name=normalize_vietnamese(doc.get("title", "")),
            validity_status=doc.get("validity_status", "Còn hiệu lực"),
            doc_type=doc.get("doc_type", ""),
            document_number=doc.get("document_number", ""),
        )
        all_chunks.extend(doc_chunks)
        
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

if __name__ == "__main__":
    # Test article-based chunking with local sample files
    test_files = [
        "vanbanphapluat_reference/luat1.html",
        "vanbanphapluat_reference/table class detailcontent.html"
    ]
    
    for file_path in test_files:
        if os.path.exists(file_path):
            print(f"\n\x1b[34m{'='*20} TESTING: {file_path} {'='*20}\x1b[0m")
            with open(file_path, 'r', encoding='utf-8') as f:
                html = f.read()
            
            chunks = chunk_html_by_article(html, "test-doc-id", "Luật Sửa đổi TTHS")
            for i, c in enumerate(chunks):
                print(f"\n\x1b[33m[Chunk {i}]\x1b[0m")
                print(f" \x1b[1mMETADATA:\x1b[0m {c.article_id}")
                content_preview = c.content.replace('\n', ' ')[:300]
                print(f" \x1b[1mCONTENT:\x1b[0m {content_preview}...")
                if i >= 10: # Only show first 10 for quick review
                    print(f"\n... and {len(chunks)-11} more chunks")
                    break
        else:
            print(f"File not found: {file_path}")
