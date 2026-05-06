#!/usr/bin/env python3
"""
Build Neo4j Graph for Legal AI.
Extracts documents, chunks, and relationships to construct:
1. (:LawDocument) nodes
2. (:Article) nodes
3. [:HAS_ARTICLE] relationships
4. Semantic document/article relationships ([:REPLACES], [:REVOKES], [:SUPPLEMENTS])
"""

import sys
import asyncio
import logging
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database_neo4j import Neo4jManager
from src.database_sql import get_session_factory, DocLegalRelation, LegalDocument

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()

LOCAL_DOCS = "data/interim/local_docs.parquet"
LOCAL_CHUNKS = "data/interim/local_chunks.parquet"

def parse_issue_year(doc_number: str) -> int:
    """Extract year from '48/2010/QH12'"""
    try:
        parts = doc_number.split('/')
        if len(parts) > 1 and parts[1].isdigit():
            return int(parts[1])
    except Exception:
        pass
    return 0

async def build_nodes(neo4j: Neo4jManager):
    """Builds LawDocument and Article nodes."""
    console.print("[yellow]1. Loading data from local parquets...[/yellow]")
    try:
        df_docs = pd.read_parquet(LOCAL_DOCS)
        df_chunks = pd.read_parquet(LOCAL_CHUNKS)
    except FileNotFoundError as e:
        console.print(f"[red]Missing data files: {e}[/red]")
        return False

    # 1. Prepare LawDocument nodes
    docs_to_insert = []
    for _, row in df_docs.iterrows():
        docs_to_insert.append({
            "id": str(row["id"]),
            "document_number": str(row.get("document_number", "")),
            "title": str(row.get("title", "")),
            "doc_type": str(row.get("doc_type", "")),
            "validity_status": str(row.get("validity_status", "")),
            "issue_year": parse_issue_year(str(row.get("document_number", "")))
        })
    
    console.print(f"   [cyan]Upserting {len(docs_to_insert)} LawDocuments...[/cyan]")
    await neo4j.upsert_law_documents_batch(docs_to_insert)

    # 2. Prepare Article nodes
    # Filter only chunks that represent Articles ("Điều X")
    # For now, let's treat any chunk with a valid article_id as an Article node.
    articles_to_insert = []
    for _, row in df_chunks.iterrows():
        art_id_meta = str(row.get("article_id", ""))
        if not art_id_meta or art_id_meta == "Thông tin chung":
            continue
            
        doc_id = str(row["document_id"])
        
        # We need a unique ID for the article node
        # User defined schema: {document_id}::Điều_{n}
        # But `art_id_meta` could be "Khoản 1, Điều 2".
        # Let's clean it up to just the article name, e.g., "Điều 2"
        article_name = art_id_meta
        if "Điều" in art_id_meta:
            import re
            m = re.search(r'(Điều\s+\d+)', art_id_meta, re.IGNORECASE)
            if m:
                article_name = m.group(1).capitalize()
                
        node_id = f"{doc_id}::{article_name.replace(' ', '_')}"
        
        articles_to_insert.append({
            "id": node_id,
            "article_number": article_name,
            "chunk_id": str(row["chunk_id"]),
            "document_id": doc_id
        })
        
    # Deduplicate articles (since multiple chunks could belong to the same Article if we have multiple clauses)
    unique_articles = {art["id"]: art for art in articles_to_insert}.values()
    
    console.print(f"   [cyan]Upserting {len(unique_articles)} Articles...[/cyan]")
    await neo4j.upsert_articles_batch(list(unique_articles))
    return True

async def build_relations(neo4j: Neo4jManager):
    """Builds relations from PostgreSQL."""
    console.print("[yellow]2. Loading relations from PostgreSQL...[/yellow]")
    factory = get_session_factory()
    
    # We need a mapping of document_number -> document_id to resolve target_doc_id
    doc_num_to_id = {}
    async with factory() as session:
        result = await session.execute(select(LegalDocument.id, LegalDocument.document_number))
        for row in result:
            doc_id, doc_num = row
            if doc_num:
                doc_num_to_id[doc_num] = doc_id
                
        # Fetch all relations
        relations_result = await session.execute(select(DocLegalRelation))
        db_relations = relations_result.scalars().all()

    doc_level_rels = []
    art_level_rels = []

    for rel in db_relations:
        target_doc_id = rel.target_doc_id or doc_num_to_id.get(rel.target_number)
        if not target_doc_id:
            # Skip if we cannot resolve the target document
            continue
            
        if rel.level == "DOCUMENT":
            doc_level_rels.append({
                "source_id": rel.source_doc_id,
                "target_id": target_doc_id,
                "relation_type": rel.relation_type,
                "properties": {
                    "source_doc": rel.source_number,
                    "target_doc": rel.target_number
                }
            })
        elif rel.level == "ARTICLE":
            # Target Article node ID
            if rel.target_article:
                tgt_art_node_id = f"{target_doc_id}::{rel.target_article.replace(' ', '_')}"
            else:
                continue # We must have a target article for an article-level relation
                
            # Source Article node ID
            if rel.source_article:
                src_art_node_id = f"{rel.source_doc_id}::{rel.source_article.replace(' ', '_')}"
                
                art_level_rels.append({
                    "source_id": src_art_node_id,
                    "target_id": tgt_art_node_id,
                    "relation_type": rel.relation_type,
                    "properties": {
                        "source_article": rel.source_article,
                        "source_clause": rel.source_clause or "",
                        "target_article": rel.target_article,
                        "target_clause": rel.target_clause or "",
                        "source_doc": rel.source_number,
                        "target_doc": rel.target_number
                    }
                })
                
    console.print(f"   [cyan]Upserting {len(doc_level_rels)} Document-level relations...[/cyan]")
    await neo4j.upsert_relations_safe_batch(doc_level_rels, level="DOCUMENT")
    
    console.print(f"   [cyan]Upserting {len(art_level_rels)} Article-level relations...[/cyan]")
    await neo4j.upsert_relations_safe_batch(art_level_rels, level="ARTICLE")

async def main():
    neo4j = Neo4jManager()
    await neo4j.connect()
    
    try:
        success = await build_nodes(neo4j)
        if success:
            await build_relations(neo4j)
        console.print("[bold green]✅ Neo4j Graph successfully built![/bold green]")
    finally:
        await neo4j.close()

if __name__ == "__main__":
    asyncio.run(main())
