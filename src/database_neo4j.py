"""
Neo4j Graph Database Manager.
Handles connection and Cypher query execution for GraphRAG.
"""

from __future__ import annotations

import logging
from typing import Any

from neo4j import AsyncGraphDatabase, AsyncSession
from langsmith import traceable

from .config import settings

logger = logging.getLogger(__name__)


class Neo4jManager:
    """Manages all interactions with the Neo4j graph database."""

    def __init__(self) -> None:
        """Initialize the async Neo4j driver."""
        self.uri = settings.NEO4J_URI
        self.user = settings.NEO4J_USER
        self.password = settings.NEO4J_PASSWORD
        self.driver = None

    async def connect(self) -> None:
        """Connect to Neo4j database."""
        if not self.driver:
            self.driver = AsyncGraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            logger.info("Connected to Neo4j at %s", self.uri)
            await self.setup_constraints()

    async def close(self) -> None:
        """Close Neo4j connection."""
        if self.driver:
            await self.driver.close()
            self.driver = None
            logger.info("Closed Neo4j connection.")

    async def setup_constraints(self) -> None:
        """Create constraints and indexes to ensure fast queries and data integrity."""
        if not self.driver:
            return

        async with self.driver.session() as session:
            try:
                # Ensure document ID is unique and indexed
                await session.run(
                    "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:LawDocument) REQUIRE d.id IS UNIQUE"
                )
                await session.run(
                    "CREATE INDEX doc_number IF NOT EXISTS FOR (d:LawDocument) ON (d.document_number)"
                )
                # Ensure article ID is unique
                await session.run(
                    "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a.id IS UNIQUE"
                )
                logger.info("Neo4j constraints and indexes ensured.")
            except Exception as e:
                logger.warning("Failed to setup Neo4j constraints: %s", e)

    async def execute_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results as a list of dicts.
        """
        if not self.driver:
            await self.connect()

        async def _run_transaction(tx):
            result = await tx.run(query, parameters or {})
            records = await result.data()
            return records

        async with self.driver.session() as session:
            try:
                # Use execute_write because we might be running CREATE/MERGE queries
                return await session.execute_write(_run_transaction)
            except Exception as e:
                logger.error("Error executing Neo4j query: %s\nQuery: %s", e, query)
                raise

    @traceable(name="Neo4j: Upsert LawDocument Batch")
    async def upsert_law_documents_batch(self, documents: list[dict[str, Any]]) -> None:
        """Batch upsert LawDocument nodes."""
        query = """
        UNWIND $documents AS doc
        MERGE (d:LawDocument {id: doc.id})
        SET d.document_number = doc.document_number,
            d.title = doc.title,
            d.doc_type = doc.doc_type,
            d.validity_status = doc.validity_status,
            d.issue_year = doc.issue_year
        """
        await self.execute_query(query, {"documents": documents})

    @traceable(name="Neo4j: Upsert Article Batch")
    async def upsert_articles_batch(self, articles: list[dict[str, Any]]) -> None:
        """
        Batch upsert Article nodes and link them to their parent LawDocument.
        Requires dicts with: id, article_number, chunk_id, document_id.
        """
        query = """
        UNWIND $articles AS art
        MERGE (a:Article {id: art.id})
        SET a.article_number = art.article_number,
            a.chunk_id = art.chunk_id,
            a.document_id = art.document_id
        WITH a, art
        MATCH (d:LawDocument {id: art.document_id})
        MERGE (d)-[:HAS_ARTICLE]->(a)
        """
        await self.execute_query(query, {"articles": articles})

    @traceable(name="Neo4j: Upsert Document Relations Batch")
    async def upsert_document_relations_batch(self, relations: list[dict[str, Any]]) -> None:
        """
        Batch upsert DOCUMENT-level relations between LawDocuments.
        Requires dicts with: source_doc_id, target_doc_id, relation_type.
        """
        query = """
        UNWIND $relations AS rel
        MATCH (src:LawDocument {id: rel.source_doc_id})
        MATCH (tgt:LawDocument {id: rel.target_doc_id})
        CALL apoc.create.relationship(src, rel.relation_type, {}, tgt)
        YIELD rel AS r
        RETURN count(r)
        """
        # Note: APOC is required for dynamic relationship types.
        # If APOC is not available, we have to group by relation_type and run separate queries.
        # Since relation_types are limited (REPLACES, REVOKES, SUPPLEMENTS), let's do it safely without APOC:
        pass # Replaced by the safe method below

    async def upsert_relations_safe_batch(self, relations: list[dict[str, Any]], level: str) -> None:
        """
        Safely batch upsert relations without requiring APOC, grouping by relationship_type.
        relations should contain: source_id, target_id, relation_type, and properties (dict).
        `level` must be "DOCUMENT" or "ARTICLE".
        """
        by_type = {}
        for r in relations:
            rt = r["relation_type"]
            if rt not in by_type:
                by_type[rt] = []
            by_type[rt].append(r)

        node_label = "LawDocument" if level == "DOCUMENT" else "Article"

        for rt, rels in by_type.items():
            # Validate rel_type to prevent injection
            if rt not in ["REPLACES", "REVOKES", "SUPPLEMENTS"]:
                logger.warning("Skipping unknown relation type: %s", rt)
                continue

            query = f"""
            UNWIND $rels AS r
            MATCH (src:{node_label} {{id: r.source_id}})
            MATCH (tgt:{node_label} {{id: r.target_id}})
            MERGE (src)-[rel:{rt}]->(tgt)
            SET rel += r.properties
            """
            await self.execute_query(query, {"rels": rels})


    @traceable(name="Neo4j: Get Related Documents")
    async def get_related_documents(self, doc_id: str, limit: int = 3) -> list[str]:
        """
        Fetch related document IDs from Neo4j for a given doc_id.
        """
        query = """
        MATCH (d:LawDocument {id: $doc_id})-[r]-(related:LawDocument)
        RETURN related.id as related_id
        LIMIT $limit
        """
        try:
            results = await self.execute_query(query, {"doc_id": doc_id, "limit": limit})
            return [str(record["related_id"]) for record in results]
        except Exception as e:
            logger.warning("Failed to fetch related documents for %s: %s", doc_id, e)
            return []

    @traceable(name="Neo4j: Get Related Chunks")
    async def get_related_chunks(self, chunk_id: str, limit: int = 3) -> list[dict[str, Any]]:
        """
        Fetch related Article chunks from Neo4j given a chunk_id.
        Traverses Article -> Article relationships.
        """
        query = """
        MATCH (a:Article {chunk_id: $chunk_id})-[r]-(related:Article)
        WHERE type(r) IN ['SUPPLEMENTS', 'REPLACES', 'REVOKES']
        RETURN related.chunk_id as related_chunk_id, type(r) as relation_type, properties(r) as properties, related.article_number as target_article
        LIMIT $limit
        """
        try:
            return await self.execute_query(query, {"chunk_id": chunk_id, "limit": limit})
        except Exception as e:
            logger.warning("Failed to fetch related chunks for %s: %s", chunk_id, e)
            return []
