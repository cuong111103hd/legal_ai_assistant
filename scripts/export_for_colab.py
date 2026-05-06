import os
import sys
import pandas as pd
from rich.console import Console

# Cho phép import từ src
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.ingestion import chunk_html_by_article, _load_dataset

console = Console()

def export_for_colab():
    console.print("[yellow]Đang load và filter dataset từ src.ingestion._load_dataset()...[/yellow]")
    documents_metadata = _load_dataset()

    if not documents_metadata:
        console.print("[red]Không tìm thấy văn bản nào thỏa mãn điều kiện lọc.[/red]")
        return

    console.print(f"[green]Đã filter còn {len(documents_metadata)} documents. Đang chunking...[/green]")

    all_chunks = []

    for doc_dict in documents_metadata:
        doc_chunks = chunk_html_by_article(
            html_content=doc_dict["content_html"],
            document_id=doc_dict["id"],
            law_name=doc_dict["title"],
            validity_status=doc_dict["validity_status"],
            doc_type=doc_dict["doc_type"],
            document_number=doc_dict["document_number"],
        )
        
        for c in doc_chunks:
            all_chunks.append(c.model_dump())

    if not all_chunks:
        console.print("[red]Không tạo được chunk nào. Kiểm tra lại dữ liệu.[/red]")
        return

    os.makedirs("data/interim", exist_ok=True)

    # 1. File gửi lên Colab (chỉ cần id và text để nhúng)
    df_to_embed = pd.DataFrame(all_chunks)[["chunk_id", "content"]]
    df_to_embed.to_parquet("data/interim/to_embed.parquet", index=False)

    # 2. File giữ lại Local (chứa toàn bộ metadata)
    df_chunks_local = pd.DataFrame(all_chunks)
    df_chunks_local.to_parquet("data/interim/local_chunks.parquet", index=False)

    df_docs_local = pd.DataFrame(documents_metadata)
    df_docs_local.to_parquet("data/interim/local_docs.parquet", index=False)

    console.print(f"\n[bold green]Đã xuất thành công {len(all_chunks)} chunks![/bold green]")
    console.print("- Gửi lên Colab: [cyan]data/interim/to_embed.parquet[/cyan]")
    console.print("- Giữ lại máy: [cyan]data/interim/local_chunks.parquet[/cyan] & [cyan]local_docs.parquet[/cyan]")

if __name__ == "__main__":
    export_for_colab()
