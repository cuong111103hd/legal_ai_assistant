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
                    "CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:LegalDocument) REQUIRE d.doc_id IS UNIQUE"
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

    @traceable(name="Neo4j: Get Related Documents")
    async def get_related_documents(self, doc_id: str, limit: int = 3) -> list[str]:
        """
        Fetch related document IDs from Neo4j for a given doc_id.
        Returns a list of doc_ids.
        """
        query = """
        MATCH (d:LegalDocument {doc_id: $doc_id})-[r:RELATES_TO]-(related:LegalDocument)
        RETURN related.doc_id as related_id
        LIMIT $limit
        """
        try:
            results = await self.execute_query(query, {"doc_id": doc_id, "limit": limit})
            return [str(record["related_id"]) for record in results]
        except Exception as e:
            logger.warning("Failed to fetch related documents for %s: %s", doc_id, e)
            return []
