#!/usr/bin/env python3
"""
Ingest relationships from HuggingFace dataset into Neo4j.

This script:
1. Downloads relationships.parquet from HuggingFace
2. Queries the Postgres database to get a list of valid document IDs (so we only load relationships for docs we actually have)
3. Loads relationship data (doc_id, other_doc_id, relationship_type) and filters it
4. Creates relationships in Neo4j between legal documents
5. Supports batch processing with progress tracking

Usage:
    python scripts/ingest_relationships.py --limit 1000
    python scripts/ingest_relationships.py --limit 50000 --batch-size 500
    python scripts/ingest_relationships.py  # Ingest all valid relationships
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import logging

import polars as pl
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from src.database_neo4j import Neo4jManager
from src.database_sql import _get_engine, LegalDocument
from sqlalchemy import select

logger = logging.getLogger(__name__)
console = Console()

# Cache directory
CACHE_DIR = Path("data/raw")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def download_relationships_parquet(use_cache: bool = True) -> Path:
    """Download relationships.parquet from HuggingFace."""
    import aiohttp
    
    dataset_name = "th1nhng0/vietnamese-legal-documents"
    url = f"https://huggingface.co/datasets/{dataset_name}/resolve/main/data/relationships.parquet"
    cache_path = CACHE_DIR / "relationships.parquet"
    
    if use_cache and cache_path.exists():
        size_mb = cache_path.stat().st_size / 1024 / 1024
        console.print(f"[green]✓ Using cached relationships.parquet ({size_mb:.1f} MB)[/green]")
        return cache_path
    
    console.print(f"[cyan]⬇️  Downloading relationships.parquet from HuggingFace...[/cyan]")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            total_size = int(response.headers.get("Content-Length", 0))
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                task = progress.add_task("Downloading relationships.parquet", total=total_size)
                
                downloaded = 0
                with open(cache_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress.update(task, advance=len(chunk))
    
    size_mb = cache_path.stat().st_size / 1024 / 1024
    console.print(f"[green]✓ Downloaded relationships.parquet ({size_mb:.1f} MB)[/green]")
    return cache_path


async def get_valid_document_ids() -> set[str]:
    """Fetch all valid document IDs from Postgres to filter relationships."""
    console.print("[yellow]🔍 Querying Postgres for valid document IDs...[/yellow]")
    valid_ids = set()
    
    engine = _get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(select(LegalDocument.id))
        for row in result:
            valid_ids.add(row[0])
            
    console.print(f"[green]✓ Found {len(valid_ids)} valid documents in Postgres.[/green]")
    return valid_ids


def load_relationships(parquet_path: Path, valid_ids: set[str], limit: int | None = None) -> pl.DataFrame:
    """Load and filter relationships using Polars."""
    console.print(f"\n[yellow]📊 Loading relationships from {parquet_path}...[/yellow]")
    
    # Read parquet
    df = pl.read_parquet(parquet_path)
    initial_count = len(df)
    console.print(f"  Found {initial_count:,} raw relationships.")
    
    # Select needed columns
    df = df.select(["doc_id", "other_doc_id", "relationship"])
    
    # Rename columns to match Neo4j logic (doc_id, other_doc_id, rel_type)
    df = df.rename({
        "relationship": "rel_type"
    })
    
    # Remove nulls
    df = df.drop_nulls()
    
    # Filter to only include relationships where BOTH documents exist in our Postgres DB
    console.print("[yellow]✂️  Filtering relationships to match Postgres DB...[/yellow]")
    
    valid_ids_list = list(valid_ids)
    
    # Cast to String permanently so Neo4j receives strings, not integers
    df = df.with_columns([
        pl.col("doc_id").cast(pl.String),
        pl.col("other_doc_id").cast(pl.String)
    ])
    
    df = df.filter(
        pl.col("doc_id").is_in(valid_ids_list) & 
        pl.col("other_doc_id").is_in(valid_ids_list)
    )
    
    filtered_count = len(df)
    console.print(f"[green]✓ Kept {filtered_count:,} valid relationships ({(filtered_count/initial_count)*100:.1f}%).[/green]")
    
    if limit:
        df = df.head(limit)
        console.print(f"  Applied limit: {limit:,}")
        
    return df


async def ingest_to_neo4j(df: pl.DataFrame, batch_size: int = 1000):
    """Ingest relationships to Neo4j in batches."""
    neo4j = Neo4jManager()
    await neo4j.connect()
    
    try:
        # Get unique document IDs from both sides of the relationships
        console.print("\n[yellow]🏗️  Preparing nodes (documents)...[/yellow]")
        doc_ids = set(df["doc_id"].to_list()) | set(df["other_doc_id"].to_list())
        doc_list = list(doc_ids)
        
        # Create nodes in batches
        node_query = """
        UNWIND $batch AS doc_id
        MERGE (d:LegalDocument {doc_id: doc_id})
        """
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Creating nodes..."),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Nodes", total=len(doc_list))
            
            for i in range(0, len(doc_list), batch_size):
                batch = doc_list[i:i + batch_size]
                await neo4j.execute_query(node_query, {"batch": batch})
                progress.update(task, advance=len(batch))
        
        console.print(f"[green]✓ Ensured {len(doc_list):,} document nodes exist.[/green]")
        
        # Create relationships in batches
        console.print("\n[yellow]🔗 Creating relationships...[/yellow]")
        
        # Convert df to list of dicts for Neo4j UNWIND
        # Keep track of unique relation types to map them to valid Cypher relationship types
        # Cypher relationship types can't have spaces or special characters easily
        # So we use a generic RELATES_TO and store the actual type as a property
        rel_query = """
        UNWIND $batch AS rel
        MATCH (a:LegalDocument {doc_id: rel.doc_id})
        MATCH (b:LegalDocument {doc_id: rel.other_doc_id})
        MERGE (a)-[r:RELATES_TO {type: rel.rel_type}]->(b)
        """
        
        rel_records = df.to_dicts()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Creating relationships..."),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Relations", total=len(rel_records))
            
            for i in range(0, len(rel_records), batch_size):
                batch = rel_records[i:i + batch_size]
                await neo4j.execute_query(rel_query, {"batch": batch})
                progress.update(task, advance=len(batch))
                
        console.print(f"[green]✓ Created {len(rel_records):,} relationships.[/green]")
        
    finally:
        await neo4j.close()


async def main():
    parser = argparse.ArgumentParser(description="Ingest legal relationships to Neo4j")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of relationships to ingest")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for Neo4j ingestion")
    parser.add_argument("--no-cache", action="store_true", help="Force re-download of parquet file")
    
    args = parser.parse_args()
    
    console.print("\n[bold cyan]🚀 Starting Relationship Ingestion for Neo4j[/bold cyan]")
    start_time = time.time()
    
    # 1. Download data
    parquet_path = await download_relationships_parquet(use_cache=not args.no_cache)
    
    # 2. Get valid document IDs from Postgres
    valid_ids = await get_valid_document_ids()
    
    if not valid_ids:
        console.print("[red]❌ No documents found in Postgres. Please run document ingestion first![/red]")
        return
        
    # 3. Load and filter relationships
    df = load_relationships(parquet_path, valid_ids, args.limit)
    
    if len(df) == 0:
        console.print("[yellow]⚠️  No valid relationships found for the documents in your database.[/yellow]")
        return
        
    # 4. Ingest to Neo4j
    await ingest_to_neo4j(df, args.batch_size)
    
    elapsed = time.time() - start_time
    console.print(f"\n[bold green]✅ Ingestion completed successfully in {elapsed:.1f} seconds![/bold green]")


if __name__ == "__main__":
    # Setup basic logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    asyncio.run(main())
