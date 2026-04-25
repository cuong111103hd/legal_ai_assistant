import logging
import os
import re
import asyncio
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import pandas as pd
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from rich.console import Console
from rich.table import Table

from .config import settings
from .database import QdrantManager
from .database_sql import (
    upsert_legal_documents_batch,
)
from .models import (
    IngestState,
    IngestStatus,
    LegalChunk,
)

logger = logging.getLogger(__name__)
console = Console()

# ---------------------------------------------------------------------------
# Module-level ingestion status & Stop Signal
# ---------------------------------------------------------------------------
_ingest_status = IngestStatus()
_stop_requested = False

def get_ingest_status() -> IngestStatus:
    return _ingest_status

def stop_ingestion_task():
    global _stop_requested
    _stop_requested = True
    logger.warning("🛑 Stop requested by user.")

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
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    container = soup.find("div", {"align": "justify"}) or soup.find("td", {"colspan": "3"}) or soup
    
    chunks: list[LegalChunk] = []
    current_article_id = None
    current_content = []
    
    article_pattern = re.compile(r"^\s*Điều\s+(\d+[a-z]?)\s*\.", re.IGNORECASE)

    for tag in container.find_all(['p', 'h3', 'h2', 'h1', 'div']):
        text = tag.get_text().strip()
        if not text:
            continue
            
        match = article_pattern.match(text)
        if match:
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
            current_article_id = text
            current_content = []
        elif current_article_id is not None:
            current_content.append(text)

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
# Load Dataset (Local Only)
# ---------------------------------------------------------------------------

def _load_dataset(limit: Optional[int] = None, doc_numbers: Optional[list[str]] = None, force_all: bool = False):
    LOCAL_META = "data/raw/metadata.parquet"
    LOCAL_CONTENT = "data/raw/content.parquet"

    if not os.path.exists(LOCAL_META) or not os.path.exists(LOCAL_CONTENT):
        raise FileNotFoundError("Local parquet files not found.")

    meta_df = pd.read_parquet(LOCAL_META)
    content_df = pd.read_parquet(LOCAL_CONTENT)
    meta_df["id"] = meta_df["id"].astype(str)
    content_df["id"] = content_df["id"].astype(str)
    
    df = pd.merge(content_df, meta_df, on="id", how="left")
    
    if force_all:
        if limit: df = df.head(limit)
    elif doc_numbers:
        if 'so_ky_hieu' in df.columns:
            df = df[df['so_ky_hieu'].astype(str).isin(doc_numbers)]
    else:
        if 'loai_van_ban' in df.columns:
            # target_types = ['Luật', 'Bộ luật', 'Nghị định', 'Thông tư', 'Nghị quyết']
            target_types = ['Luật', 'Bộ luật']
            df = df[df['loai_van_ban'].astype(str).isin(target_types)]
        if 'tinh_trang_hieu_luc' in df.columns:
            target_status = ['Còn hiệu lực', 'Hết hiệu lực một phần']
            df = df[df['tinh_trang_hieu_luc'].astype(str).isin(target_status)]
        if 'ngay_ban_hanh' in df.columns:
            df['dt_ban_hanh'] = pd.to_datetime(df['ngay_ban_hanh'], format='%d/%m/%Y', errors='coerce')
            df = df[df['dt_ban_hanh'].dt.year >= 2015]

        # Quality Filters (SMART FILTERING)
        # Skip empty or very short HTML content (< 200 characters)
        df = df[df['content_html'].str.len() > 200]
        
        # Skip documents that don't contain "Điều X" (not a structured legal document)
        df = df[df['content_html'].str.contains(r'Điều\s+\d+', case=False, regex=True)]

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
    return merged

# ---------------------------------------------------------------------------
# Ingestion Pipeline (Asynchronous & Thread-safe)
# ---------------------------------------------------------------------------

async def run_full_ingestion(limit: Optional[int] = None) -> IngestStatus:
    global _ingest_status, _stop_requested
    _ingest_status = IngestStatus(state=IngestState.RUNNING, processed_documents=0, total_documents=0)
    _stop_requested = False

    try:
        console.print(f"\n[bold magenta]🏗️  Ingestion Starting (Limit: {limit or 'All'})[/bold magenta]")
        
        # Load dataset in a thread to keep event loop responsive
        documents = await asyncio.to_thread(_load_dataset, limit=limit)
        _ingest_status.total_documents = len(documents)

        if not documents:
            _ingest_status.state = IngestState.FAILED
            _ingest_status.error_message = "No documents found."
            return _ingest_status

        await upsert_legal_documents_batch(documents)
        
        # Chunking with Stop Signal Checks
        all_chunks = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("  Chunking", total=len(documents))
            for doc in documents:
                if _stop_requested:
                    _ingest_status.state = IngestState.FAILED
                    _ingest_status.error_message = "Dừng nạp bởi người dùng."
                    console.print("[bold red]🛑 Stopped during Chunking.[/bold red]")
                    return _ingest_status
                
                # BS4 is fast but we can thread it if needed. For now, just keep it here.
                doc_chunks = chunk_html_by_article(
                    html_content=doc["content_html"],
                    document_id=doc["id"],
                    law_name=doc["title"],
                    validity_status=doc["validity_status"],
                    doc_type=doc["doc_type"],
                    document_number=doc["document_number"],
                )
                all_chunks.extend(doc_chunks)
                _ingest_status.processed_documents += 1
                progress.update(task, advance=1)
                
                # Crucial: Yield control back to event loop for a microsecond
                await asyncio.sleep(0)

        _ingest_status.total_chunks = len(all_chunks)
        
        # Embedding (HEAVY CPU TASK) - MUST BE IN THREAD
        console.print(f"[yellow]🧬 Embedding {len(all_chunks)} chunks...[/yellow]")
        model = SentenceTransformer(settings.EMBEDDING_MODEL)
        
        batch_size = 32
        embeddings = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[yellow]{task.description}"),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=True,
        ) as progress:
            emb_task = progress.add_task("  Embedding", total=len(all_chunks))
            
            for i in range(0, len(all_chunks), batch_size):
                if _stop_requested:
                    _ingest_status.state = IngestState.FAILED
                    _ingest_status.error_message = "Dừng nạp bởi người dùng."
                    console.print("[bold red]🛑 Stopped during Embedding.[/bold red]")
                    return _ingest_status
                
                batch_texts = [c.content for c in all_chunks[i:i + batch_size]]
                
                # RUN CPU TASK IN THREAD TO PREVENT SERVER HANG
                batch_embeddings = await asyncio.to_thread(model.encode, batch_texts, show_progress_bar=False)
                
                embeddings.extend(batch_embeddings)
                progress.update(emb_task, advance=len(batch_texts))
                
                # Yield control
                await asyncio.sleep(0)

        # Vector DB Upsert
        console.print("[yellow]📦 Upserting to Qdrant...[/yellow]")
        db = QdrantManager()
        db.create_collection(recreate=True)
        db.upsert_batch(all_chunks, embeddings)

        _ingest_status.state = IngestState.COMPLETED
        
        table = Table(title="Ingestion Complete", show_header=False, border_style="green")
        table.add_row("Documents", f"[bold green]{_ingest_status.processed_documents}[/bold green]")
        table.add_row("Chunks", f"[bold green]{_ingest_status.total_chunks}[/bold green]")
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        _ingest_status.state = IngestState.FAILED
        _ingest_status.error_message = str(e)

    return _ingest_status

async def run_test_ingestion(limit: int = 50) -> IngestStatus:
    return await run_full_ingestion(limit=limit)

async def run_ingestion_by_numbers(doc_numbers: list[str]) -> IngestStatus:
    # (Tương tự, cũng cần đẩy vào thread nếu bạn nạp số lượng cực lớn)
    return await run_full_ingestion(limit=None) # Simplified for now
