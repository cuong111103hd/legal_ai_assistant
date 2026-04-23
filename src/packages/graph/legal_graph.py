import logging
from typing import Any, Dict, List, Optional
from neo4j import AsyncGraphDatabase, Driver
from src.config import settings

logger = logging.getLogger(__name__)

class LegalGraphClient:
    """
    Client for interacting with the Neo4j graph database for legal relationships.
    """

    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.driver: Optional[Driver] = None

    async def connect(self):
        """Establish connection to Neo4j."""
        if not self.driver:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            logger.info(f"Connected to Neo4j at {self.uri}")

    async def close(self):
        """Close Neo4j connection."""
        if self.driver:
            await self.driver.close()
            self.driver = None

    async def verify_connectivity(self) -> bool:
        """Check if Neo4j is reachable."""
        try:
            if not self.driver:
                await self.connect()
            await self.driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Neo4j connectivity check failed: {e}")
            return False

    async def ensure_schema(self):
        """Initialize indexes and constraints."""
        if not self.driver:
            await self.connect()
        
        async with self.driver.session() as session:
            # Create uniqueness constraint on document_id
            await session.run(
                "CREATE CONSTRAINT legal_doc_id_unique IF NOT EXISTS "
                "FOR (n:LegalDocument) REQUIRE n.document_id IS UNIQUE"
            )
            # Create index on document_number for faster lookup
            await session.run(
                "CREATE INDEX legal_doc_num_idx IF NOT EXISTS "
                "FOR (n:LegalDocument) ON (n.document_number)"
            )
            logger.info("Neo4j schema (constraints/indexes) ensured.")

    async def add_document_node(self, document_id: str, title: str, doc_type: str, document_number: str):
        """Create or update a LegalDocument node."""
        if not self.driver:
            await self.connect()
            
        cypher = """
        MERGE (d:LegalDocument {document_id: $document_id})
        SET d.title = $title,
            d.doc_type = $doc_type,
            d.document_number = $document_number,
            d.updated_at = datetime()
        """
        async with self.driver.session() as session:
            await session.run(cypher, {
                "document_id": document_id,
                "title": title,
                "doc_type": doc_type,
                "document_number": document_number
            })

    async def add_relationship(self, source_id: str, target_id: str, rel_type: str):
        """Create a relationship between two legal documents."""
        if not self.driver:
            await self.connect()
            
        # Standardize relationship type (Neo4j relationship types are typically UPPER_SNAKE_CASE)
        # However, for legal docs, we might use the actual types like "VAN_BAN_HUONG_DAN"
        rel_type_clean = rel_type.replace(" ", "_").upper()
        
        cypher = f"""
        MATCH (a:LegalDocument {{document_id: $source_id}})
        MATCH (b:LegalDocument {{document_id: $target_id}})
        MERGE (a)-[r:{rel_type_clean}]->(b)
        ON CREATE SET r.created_at = datetime()
        """
        async with self.driver.session() as session:
            await session.run(cypher, {
                "source_id": source_id,
                "target_id": target_id
            })

    async def get_related_documents(self, document_id: str, rel_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch documents related to the given one."""
        if not self.driver:
            await self.connect()
            
        relationship_clause = ""
        if rel_types:
            clean_rels = [r.replace(" ", "_").upper() for r in rel_types]
            relationship_clause = ":" + "|".join(clean_rels)
            
        cypher = f"""
        MATCH (d:LegalDocument {{document_id: $document_id}})-[r{relationship_clause}]-(related)
        RETURN related.document_id as document_id, 
               related.title as title, 
               related.document_number as document_number,
               related.doc_type as doc_type,
               type(r) as relationship_type
        """
        
        async with self.driver.session() as session:
            result = await session.run(cypher, {"document_id": document_id})
            records = await result.data()
            return records
