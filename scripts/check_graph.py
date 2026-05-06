import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database_neo4j import Neo4jManager
from rich.console import Console
from rich.table import Table

async def check_graph_rag():
    console = Console()
    neo4j = Neo4jManager()
    await neo4j.connect()

    # Thay vì dùng hardcoded chunk_id, chúng ta tìm Điều 63 của Luật 55/2010/QH12
    # để demo Graph Expansion.
    console.print("[yellow]🔍 Đang tìm kiếm Node mẫu trong Neo4j (Điều 63 - 55/2010/QH12)...[/yellow]")
    
    query_find = """
    MATCH (d:LawDocument {document_number: '55/2010/QH12'})-[:HAS_ARTICLE]->(a:Article)
    WHERE a.article_number CONTAINS 'Điều 63'
    RETURN a.chunk_id as chunk_id, a.id as article_id
    """
    sample_nodes = await neo4j.execute_query(query_find)
    
    if not sample_nodes:
        console.print("[red]❌ Không tìm thấy Điều 63 của luật 55/2010/QH12 trong Neo4j.[/red]")
        await neo4j.close()
        return

    test_chunk_id = sample_nodes[0]["chunk_id"]
    console.print(f"\n[bold yellow]🔍 Kiểm tra GraphRAG Expansion cho chunk_id:[/bold yellow] {test_chunk_id} ({sample_nodes[0]['article_id']})")
    
    results = await neo4j.get_related_chunks(test_chunk_id, limit=5)
    
    if not results:
        console.print("[red]❌ Không tìm thấy quan hệ nào cho chunk này trong Neo4j.[/red]")
        console.print("[dim]Gợi ý: Đảm bảo bạn đã chạy `python scripts/build_graph.py` thành công.[/dim]")
    else:
        table = Table(title="🌿 Kết quả Graph Expansion từ Neo4j", show_header=True, header_style="bold magenta")
        table.add_column("Relationship", style="green")
        table.add_column("Target Article", style="cyan")
        table.add_column("Target Chunk ID", style="dim")
        table.add_column("Details (Properties)", style="yellow")

        for res in results:
            props = res.get("properties", {})
            details = f"Clause: {props.get('source_clause', 'N/A')} -> {props.get('target_clause', 'N/A')}\n" \
                      f"Doc: {props.get('source_doc', 'N/A')} -> {props.get('target_doc', 'N/A')}"
            
            table.add_row(
                res["relation_type"],
                res["target_article"],
                res["related_chunk_id"],
                details
            )
        
        console.print(table)
        console.print("\n[bold green]✅ Neo4j Article-level Graph is working correctly![/bold green]")

    await neo4j.close()

if __name__ == "__main__":
    asyncio.run(check_graph_rag())
