import os
import sys
import asyncio
import pandas as pd
from rich.console import Console

# Cho phép import từ src
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.database_sql import (
    init_db,
    upsert_legal_documents_batch,
    upsert_legal_relation,
    resolve_all_relations,
)
from src.database import QdrantManager
from src.database_opensearch import OpenSearchManager
from src.models import LegalChunk
from src.relation_extractor import extract_relations

console = Console()

async def import_from_colab():
    LOCAL_DOCS = "data/interim/local_docs.parquet"
    LOCAL_CHUNKS = "data/interim/local_chunks.parquet"
    COLAB_VECTORS = "data/interim/vectors.parquet"

    if not all(os.path.exists(f) for f in [LOCAL_DOCS, LOCAL_CHUNKS, COLAB_VECTORS]):
        console.print("[red]Thiếu file trong data/interim/. Đảm bảo bạn đã export và tải vectors.parquet từ Colab về.[/red]")
        return

    console.print("[yellow]1. Đang khởi tạo Database SQL...[/yellow]")
    await init_db()

    # ---- BƯỚC 1: Load và nạp Documents vào SQL ----
    console.print("[yellow]2. Đang nạp Documents vào PostgreSQL...[/yellow]")
    df_docs = pd.read_parquet(LOCAL_DOCS)
    documents = df_docs.to_dict("records")
    await upsert_legal_documents_batch(documents)
    console.print(f"[green]  ✓ Đã nạp {len(documents)} văn bản.[/green]")

    # ---- BƯỚC 2: Trích xuất và nạp quan hệ pháp lý ----
    console.print("[yellow]3. Đang trích xuất quan hệ pháp lý từ văn bản (kết hợp chunks)...[/yellow]")
    df_chunks = pd.read_parquet(LOCAL_CHUNKS)
    chunks_by_doc = df_chunks.groupby("document_id")

    relation_count = 0
    for doc in documents:
        doc_id = str(doc["id"])
        doc_chunks = chunks_by_doc.get_group(doc_id).to_dict("records") if doc_id in chunks_by_doc.groups else []
        
        rels = extract_relations(
            doc_id=doc_id,
            doc_number=doc["document_number"],
            html_content=doc["content_html"],
            title=doc["title"],
            chunks=doc_chunks,
        )
        for rel in rels:
            await upsert_legal_relation(
                source_doc_id=rel.source_doc_id,
                source_number=rel.source_number,
                target_number=rel.target_number,
                relation_type=rel.relation_type,
                level=rel.level,
                source_article=rel.source_article,
                source_clause=rel.source_clause,
                target_article=rel.target_article,
                target_clause=rel.target_clause,
            )
            relation_count += 1
    console.print(f"[green]  ✓ Tìm thấy {relation_count} quan hệ (doc + article level).[/green]")

    # ---- BƯỚC 3: Ghép nối vector với metadata và nạp vào Qdrant ----
    console.print("[yellow]4. Đang xử lý Vector từ Colab...[/yellow]")
    # Đã load df_chunks ở trên
    df_vectors = pd.read_parquet(COLAB_VECTORS)

    # Nối theo chunk_id
    df_merged = pd.merge(df_chunks, df_vectors, on="chunk_id", how="inner")
    
    all_chunks = []
    all_embeddings = []
    
    for _, row in df_merged.iterrows():
        row_dict = row.to_dict()
        vector = row_dict.pop("vector")
        
        chunk = LegalChunk(**row_dict)
        all_chunks.append(chunk)
        if isinstance(vector, list):
            all_embeddings.append(vector)
        else:
            all_embeddings.append(vector.tolist())

    if not all_chunks:
        console.print("[red]Không có chunk nào khớp sau khi nối. Kiểm tra lại file.[/red]")
        return

    console.print(f"[yellow]5. Đang Upsert {len(all_chunks)} chunks vào Qdrant...[/yellow]")
    db = QdrantManager()
    # Nếu muốn ghi đè toàn bộ DB cũ, set recreate=True. Nếu muốn thêm mới, để recreate=False.
    # Tuy nhiên vì data lớn, ta nên create_collection trước nếu chưa có.
    db.create_collection(recreate=True)
    db.upsert_batch(all_chunks, all_embeddings)
    console.print(f"[green]  ✓ Đã nạp xong Vectors![/green]")

    console.print(f"[yellow]5.5. Đang Upsert {len(all_chunks)} chunks vào OpenSearch...[/yellow]")
    os_db = OpenSearchManager()
    os_db.create_index(recreate=True)
    os_db.upsert_batch(all_chunks)
    console.print(f"[green]  ✓ Đã nạp xong OpenSearch![/green]")

    # ---- BƯỚC 4: Resolve Relations ----
    console.print("[yellow]6. Resolving Target Documents trong SQL...[/yellow]")
    resolved_count = await resolve_all_relations()
    console.print(f"[green]  ✓ Đã resolve thành công {resolved_count} quan hệ.[/green]")

    console.print("\n[bold green]🎉 Hoàn tất quy trình Import![/bold green]")

if __name__ == "__main__":
    asyncio.run(import_from_colab())
