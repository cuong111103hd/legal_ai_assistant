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
from .database_opensearch import OpenSearchManager
from .database_sql import (
    upsert_legal_documents_batch,
    upsert_legal_relation,
    resolve_all_relations,
    init_db,
)
from .relation_extractor import extract_relation
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

QUOTE_SIZE_LIMIT = 700  # Tính trên tổng: article_preamble + clause_buffer + quote_buffer


def _section_chunk(
    text: str,
    document_id: str,
    law_name: str,
    validity_status: str,
    doc_type: str,
    document_number: str,
    outer_article_id: str,   # Override article_id for all sub-chunks
    prefix_content: str,     # Outer preamble + clause content, prepended to each sub-chunk
    start_index: int,
) -> list[LegalChunk]:
    """
    Sub-chunker for long quoted sections (> QUOTE_SIZE_LIMIT).

    Mirrors the outer chunker logic:
    - inner_article_header : "Dieu X..." inside the quote — included in content
    - inner_preamble       : text between inner Dieu and first inner clause
    - Clause chunk content : prefix_content + inner_header + inner_preamble + clause
    - No-clause content    : prefix_content + inner_header + inner_preamble
    """
    article_pattern = re.compile(r"^\s*(Điều\s+\d+[a-z]?\b.*)", re.IGNORECASE)
    clause_pattern  = re.compile(r"^\s*(\d+)\s*\.", re.IGNORECASE)

    chunks: list[LegalChunk] = []

    inner_header:    str       = ""   # "Điều X..." inside quote
    inner_preamble:  list[str] = []   # text between inner Điều and first inner clause
    inner_clause:    str       = ""
    inner_clause_buf: list[str] = []
    inner_in_clause: bool      = False

    def _build_content(clause_lines: list[str]) -> str:
        """Build content: prefix + inner_header + inner_preamble + clause_lines."""
        parts = []
        if prefix_content:
            parts.append(prefix_content)
        if inner_header:
            parts.append(inner_header)
        if inner_preamble:
            parts.append("\n".join(inner_preamble))
        if clause_lines:
            parts.append("\n".join(clause_lines))
        return "\n".join(filter(None, parts))

    def _flush_inner_clause():
        nonlocal inner_clause_buf, inner_clause, inner_in_clause
        if not inner_clause_buf:
            return
        chunks.append(LegalChunk(
            chunk_id=str(uuid4()),
            document_id=document_id,
            law_name=law_name,
            article_id=outer_article_id,
            content=_build_content(inner_clause_buf),
            validity_status=validity_status,
            doc_type=doc_type,
            document_number=document_number,
            chunk_index=start_index + len(chunks),
        ))
        inner_clause_buf = []
        inner_clause = ""
        inner_in_clause = False
        # inner_preamble is kept — reused as prefix for subsequent clauses

    def _flush_inner_no_clause():
        """Flush when inner Dieu has no clauses (or end-of-text fallback)."""
        nonlocal inner_preamble, inner_header
        if not inner_header and not inner_preamble:
            return
        chunks.append(LegalChunk(
            chunk_id=str(uuid4()),
            document_id=document_id,
            law_name=law_name,
            article_id=outer_article_id,
            content=_build_content([]),
            validity_status=validity_status,
            doc_type=doc_type,
            document_number=document_number,
            chunk_index=start_index + len(chunks),
        ))
        inner_header = ""
        inner_preamble = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        art_m = article_pattern.match(line)
        if art_m:
            # Flush previous inner state before starting a new inner Dieu
            if inner_in_clause:
                _flush_inner_clause()
            else:
                _flush_inner_no_clause()
            inner_header   = line
            inner_preamble = []
            inner_clause_buf = []
            inner_clause   = ""
            inner_in_clause = False
            continue

        cls_m = clause_pattern.match(line)
        if cls_m:
            if inner_in_clause:
                _flush_inner_clause()   # inner_preamble preserved for next clause
            # First clause: inner_preamble stays as prefix, no standalone flush
            inner_clause     = cls_m.group(1)
            inner_clause_buf = [line]
            inner_in_clause  = True
            continue

        if inner_in_clause:
            inner_clause_buf.append(line)
        else:
            inner_preamble.append(line)

    # Final flush
    if inner_in_clause:
        _flush_inner_clause()
    else:
        _flush_inner_no_clause()

    return chunks



def chunk_html_by_article(
    html_content: str,
    document_id: str,
    law_name: str,
    validity_status: str = "Còn hiệu lực",
    doc_type: str = "",
    document_number: str = "",
) -> list[LegalChunk]:
    """
    Chunks HTML content into legal segments by section (Dieu/Khoan).

    Rules:
    - article_header  : "Dieu X. Title..." — used for article_id metadata ONLY.
    - article_preamble: text lines between header and first Khoan — used as
                        content prefix in every clause chunk.
    - Dieu without Khoan  → 1 chunk: (article_header + preamble).
    - Dieu with Khoan     → per Khoan: (preamble + khoan content).
    - Quote short (total ≤ QUOTE_SIZE_LIMIT): append to current buffer.
    - Quote long          : _section_chunk splits by inner Dieu/Khoan;
                            each sub-chunk prefixed with outer preamble + clause.
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    container = (
        soup.find("div", class_="content1")
        or soup.find("div", {"align": "justify"})
        or soup.find("td", {"colspan": "3"})
        or soup
    )

    QUOTE_OPEN  = "\u201c"  # "
    QUOTE_CLOSE = "\u201d"  # "

    article_pattern = re.compile(r"^\s*(Điều\s+\d+[a-z]?\b.*)", re.IGNORECASE)
    clause_pattern  = re.compile(r"^\s*(\d+)\s*\.", re.IGNORECASE)

    chunks: list[LegalChunk] = []

    article_header:   str       = ""   # "Điều X. ..."  → article_id only
    article_preamble: list[str] = []   # text between header and first clause → prefix
    current_clause:   str       = ""
    clause_buffer:    list[str] = []
    in_clause:        bool      = False

    in_quote:       bool      = False
    quote_buffer:   list[str] = []
    quote_outer_id: str       = ""    # Captured once when entering quote
    quote_prefix:   str       = ""    # Captured once when entering quote

    # ── Internal flush helpers ────────────────────────────────────────────────

    def _make_chunk(article_id: str, content: str) -> None:
        if not content.strip():
            return
        chunks.append(LegalChunk(
            chunk_id=str(uuid4()),
            document_id=document_id,
            law_name=law_name,
            article_id=article_id,
            content=content,
            validity_status=validity_status,
            doc_type=doc_type,
            document_number=document_number,
            chunk_index=len(chunks),
        ))

    def flush_clause_chunk() -> None:
        """Flush current clause. article_preamble is kept as prefix for next clause."""
        nonlocal clause_buffer, current_clause, in_clause
        if not clause_buffer:
            return
        prefix = "\n".join(article_preamble)
        clause_text = "\n".join(clause_buffer)
        content = f"{prefix}\n{clause_text}" if prefix else clause_text
        _make_chunk(
            article_id=f"Khoản {current_clause}, {article_header}",
            content=content,
        )
        clause_buffer = []
        current_clause = ""
        in_clause = False

    def flush_article_chunk() -> None:
        """Flush whole article when no clauses were found. Includes header in content."""
        nonlocal article_header, article_preamble
        if not article_header and not article_preamble:
            return
        preamble_text = "\n".join(article_preamble)
        content = f"{article_header}\n{preamble_text}" if preamble_text else article_header
        _make_chunk(article_id=article_header or "Thông tin chung", content=content)
        article_header = ""
        article_preamble = []

    def flush_quote() -> None:
        """Handle quote buffer: short → append to buffer, long → _section_chunk.
        Uses quote_outer_id and quote_prefix captured when entering quote mode.
        """
        nonlocal quote_buffer
        if not quote_buffer:
            return
        full_quote = "\n".join(quote_buffer)
        quote_buffer = []

        preamble_str = "\n".join(article_preamble)
        clause_str   = "\n".join(clause_buffer)
        total_size   = len(preamble_str) + len(clause_str) + len(full_quote)

        if total_size <= QUOTE_SIZE_LIMIT:
            # Short: merge into current buffer
            if in_clause:
                clause_buffer.append(full_quote)
            else:
                article_preamble.append(full_quote)
        else:
            # Long: split by inner structure using PRE-CAPTURED prefix
            sub = _section_chunk(
                text=full_quote,
                document_id=document_id,
                law_name=law_name,
                validity_status=validity_status,
                doc_type=doc_type,
                document_number=document_number,
                outer_article_id=quote_outer_id,
                prefix_content=quote_prefix,
                start_index=len(chunks),
            )
            chunks.extend(sub)

    # ── Main loop ─────────────────────────────────────────────────────────────

    for tag in container.find_all(["p", "h1", "h2", "h3", "div", "tr"]):
        text = tag.get_text().strip()
        if not text:
            continue

        # ── Quote mode ───────────────────────────────────────────────────────
        if in_quote:
            quote_buffer.append(text)
            if QUOTE_CLOSE in text:
                # Quote closed — flush the entire accumulated quote at once
                in_quote = False
                flush_quote()
            # No mid-quote periodic flush: accumulate the full quote so that
            # _section_chunk receives the complete inner structure in one pass.
            continue

        # ── Quote open ───────────────────────────────────────────────────────
        if QUOTE_OPEN in text:
            if QUOTE_CLOSE in text:
                # Single-line quote: treat as normal text
                if in_clause:
                    clause_buffer.append(text)
                else:
                    article_preamble.append(text)
            else:
                # Multi-line quote: capture prefix ONCE before entering quote mode
                preamble_str = "\n".join(article_preamble)
                clause_str   = "\n".join(clause_buffer)
                if in_clause:
                    quote_outer_id = f"Khoản {current_clause}, {article_header}"
                    quote_prefix   = f"{preamble_str}\n{clause_str}".strip()
                else:
                    quote_outer_id = article_header or "Thông tin chung"
                    quote_prefix   = preamble_str
                in_quote     = True
                quote_buffer = [text]
            continue

        # ── New Điều ─────────────────────────────────────────────────────────
        art_m = article_pattern.match(text)
        if art_m:
            if in_clause:
                flush_clause_chunk()
            else:
                flush_article_chunk()
            article_header   = text
            article_preamble = []
            clause_buffer    = []
            current_clause   = ""
            in_clause        = False
            continue

        # ── New Khoản ────────────────────────────────────────────────────────
        cls_m = clause_pattern.match(text)
        if cls_m and article_header:
            if in_clause:
                flush_clause_chunk()           # article_preamble preserved
            # First clause: flush_article_chunk is NOT called —
            # article_preamble stays as prefix
            current_clause = cls_m.group(1)
            clause_buffer  = [text]
            in_clause      = True
            continue

        # ── Regular content ───────────────────────────────────────────────────
        if article_header:
            if in_clause:
                clause_buffer.append(text)
            else:
                article_preamble.append(text)

    # ── Final flush ───────────────────────────────────────────────────────────
    if in_quote:
        flush_quote()
    if in_clause:
        flush_clause_chunk()
    else:
        flush_article_chunk()

    return chunks



# ---------------------------------------------------------------------------
# Load Dataset (Local Only)
# ---------------------------------------------------------------------------


def _load_dataset(limit: Optional[int] = None, doc_numbers: Optional[list[str]] = None, force_all: bool = False, prefix: str = ""):
    LOCAL_META = f"data/raw/{prefix}metadata.parquet"
    LOCAL_CONTENT = f"data/raw/{prefix}content.parquet"

    if not os.path.exists(LOCAL_META) or not os.path.exists(LOCAL_CONTENT):
        raise FileNotFoundError("Local parquet files not found.")

    meta_df = pd.read_parquet(LOCAL_META)
    content_df = pd.read_parquet(LOCAL_CONTENT)
    meta_df["id"] = meta_df["id"].astype(str)
    content_df["id"] = content_df["id"].astype(str)
    
    df = pd.merge(content_df, meta_df, on="id", how="left")
    
    # Ưu tiên giữ lại bản ghi có nội dung (content_html) dài nhất/đầy đủ nhất
    if 'content_html' in df.columns:
        # Tạo cột tạm tính độ dài để sort
        df['_content_len'] = df['content_html'].astype(str).str.len()
        df = df.sort_values(by=['id', '_content_len'], ascending=[True, False])
        df = df.drop_duplicates(subset=["id"], keep="first")
        df = df.drop(columns=['_content_len'])
    else:
        df = df.drop_duplicates(subset=["id"], keep="first")
    
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
            df = df[df['dt_ban_hanh'].dt.year >= 2000]
            
        if 'content_html' in df.columns:
            df = df[df['content_html'].astype(str).str.len() > 500]

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


def _load_dataset_by_type(doc_types: list[str], limit: Optional[int] = None) -> list[dict]:
    """Load documents filtered by specific loai_van_ban types (e.g. ['Bộ luật'])."""
    LOCAL_META = "data/raw/metadata.parquet"
    LOCAL_CONTENT = "data/raw/content.parquet"

    if not os.path.exists(LOCAL_META) or not os.path.exists(LOCAL_CONTENT):
        raise FileNotFoundError("Local parquet files not found.")

    meta_df = pd.read_parquet(LOCAL_META)
    content_df = pd.read_parquet(LOCAL_CONTENT)
    meta_df["id"] = meta_df["id"].astype(str)
    content_df["id"] = content_df["id"].astype(str)

    df = pd.merge(content_df, meta_df, on="id", how="left")

    if "loai_van_ban" in df.columns:
        df = df[df["loai_van_ban"].astype(str).isin(doc_types)]

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

async def run_ingestion_pipeline(limit: Optional[int] = None, prefix: str = "", recreate: bool = True) -> IngestStatus:
    global _ingest_status, _stop_requested
    _ingest_status = IngestStatus(state=IngestState.RUNNING, processed_documents=0, total_documents=0)
    _stop_requested = False

    try:
        console.print(f"\n[bold magenta]🏗️  Ingestion Starting (Limit: {limit or 'All'})[/bold magenta]")

        # Ensure all tables exist (creates doc_legal_relations if new)
        await init_db()

        # Load dataset in a thread to keep event loop responsive
        documents = await asyncio.to_thread(_load_dataset, limit=limit, prefix=prefix)
        _ingest_status.total_documents = len(documents)

        if not documents:
            _ingest_status.state = IngestState.FAILED
            _ingest_status.error_message = "No documents found."
            return _ingest_status

        await upsert_legal_documents_batch(documents)

        # ── Step 2: Extract legal relations from preamble ────────────────────
        console.print("[yellow]🔗 Extracting legal relations...[/yellow]")
        relation_count = 0
        for doc in documents:
            rel = extract_relation(
                doc_id=doc["id"],
                doc_number=doc["document_number"],
                html_content=doc["content_html"],
                title=doc["title"],
            )
            if rel:
                await upsert_legal_relation(
                    source_doc_id=rel.source_doc_id,
                    source_number=rel.source_number,
                    target_number=rel.target_number,
                    relation_type=rel.relation_type,
                )
                relation_count += 1
        console.print(f"[green]  ✓ Found and stored {relation_count} legal relations.[/green]")

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
        console.print(f"[yellow]📦 Upserting to Qdrant (recreate={recreate})...[/yellow]")
        db = QdrantManager()
        db.create_collection(recreate=recreate)
        db.upsert_batch(all_chunks, embeddings)

        # OpenSearch Lexical DB Upsert
        console.print(f"[yellow]📦 Upserting to OpenSearch (recreate={recreate})...[/yellow]")
        os_db = OpenSearchManager()
        os_db.create_index(recreate=recreate)
        os_db.upsert_batch(all_chunks)



        # ── Step 5: Resolve target_doc_id for all unresolved relations ───────
        console.print("[yellow]🔍 Resolving legal relations...[/yellow]")
        resolved = await resolve_all_relations()
        console.print(f"[green]  ✓ Resolved {resolved} legal relation(s) to doc IDs.[/green]")

        _ingest_status.state = IngestState.COMPLETED

        table = Table(title="Ingestion Complete", show_header=False, border_style="green")
        table.add_row("Documents",          f"[bold green]{_ingest_status.processed_documents}[/bold green]")
        table.add_row("Chunks",             f"[bold green]{_ingest_status.total_chunks}[/bold green]")
        table.add_row("Relations extracted", f"[bold cyan]{relation_count}[/bold cyan]")
        table.add_row("Relations resolved",  f"[bold cyan]{resolved}[/bold cyan]")
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]❌ Error: {e}[/bold red]")
        _ingest_status.state = IngestState.FAILED
        _ingest_status.error_message = str(e)

    return _ingest_status

async def run_test_ingestion(limit: int = 50) -> IngestStatus:
    return await run_ingestion_pipeline(limit=limit)

async def run_ingestion_by_numbers(doc_numbers: list[str]) -> IngestStatus:
    # (Tương tự, cũng cần đẩy vào thread nếu bạn nạp số lượng cực lớn)
    return await run_ingestion_pipeline(limit=None) # Simplified for now

if __name__ == "__main__":
    async def test_chunking_by_id(doc_id: str):
        console.print(f"[bold cyan]🧪 Testing Chunking for Document ID: {doc_id}[/bold cyan]")
        try:
            # 1. Load document by ID
            # We reuse _load_dataset but filter for our ID
            LOCAL_META = "data/raw/addition_metadata.parquet"
            LOCAL_CONTENT = "data/raw/addition_content.parquet"
            
            meta_df = pd.read_parquet(LOCAL_META)
            content_df = pd.read_parquet(LOCAL_CONTENT)
            meta_df["id"] = meta_df["id"].astype(str)
            content_df["id"] = content_df["id"].astype(str)
            
            df = pd.merge(content_df, meta_df, on="id", how="left")
            doc_row = df[df["id"] == doc_id]
            
            if doc_row.empty:
                console.print(f"[bold red]❌ Document ID {doc_id} not found in dataset.[/bold red]")
                return

            doc = doc_row.iloc[0].to_dict()
            
            # Prepare metadata for chunking
            title = doc.get("title", doc.get("trich_yeu", "Unknown Title"))
            document_number = doc.get("so_ky_hieu", "")
            doc_type = doc.get("loai_van_ban", "")
            validity_status = doc.get("tinh_trang_hieu_luc", "Còn hiệu lực")

            console.print(f"Document: [green]{title}[/green] (Number: [yellow]{document_number}[/yellow])")

            # 2. Perform chunking
            chunks = chunk_html_by_article(
                html_content=doc["content_html"],
                document_id=doc_id,
                law_name=title,
                validity_status=validity_status,
                doc_type=doc_type,
                document_number=document_number,
            )

            console.print(f"Total chunks generated: [bold blue]{len(chunks)}[/bold blue]")
            console.print(f"[bold yellow]Displaying first 10 chunks (100 characters each):[/bold yellow]")
            console.print("=" * 80)

            for i, chunk in enumerate(chunks[:10]):
                # Lấy đúng 100 ký tự đầu tiên
                full_100 = chunk.content[:200]
                # Thay thế xuống dòng bằng dấu cách để không làm vỡ giao diện list, 
                # nhưng vẫn giữ nguyên độ dài.
                display_text = full_100.replace("\n", " ")
                
                console.print(f"[bold green]#{i+1}[/bold green] | [bold cyan]{chunk.article_id}[/bold cyan] | Index: {chunk.chunk_index}")
                console.print(f"[white]{display_text}[/white]")
                if len(chunk.content) > 100:
                    console.print("[dim]... (còn tiếp)[/dim]")
                console.print("-" * 80)

        except Exception as e:
            console.print(f"[bold red]Test failed: {e}[/bold red]")
            import traceback
            traceback.print_exc()

    import asyncio
    # Bạn có thể thay đổi ID ở đây để test các văn bản khác nhau
    FIXED_DOC_ID = "1777626241" 
    asyncio.run(test_chunking_by_id(FIXED_DOC_ID))
