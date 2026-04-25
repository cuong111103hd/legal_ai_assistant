import asyncio
from src.database_neo4j import Neo4jManager

async def main():
    manager = Neo4jManager()
    await manager.connect()
    print("Fixing doc_id types in Neo4j...")
    await manager.execute_query("MATCH (n:LegalDocument) SET n.doc_id = toString(n.doc_id)")
    print("✅ Fixed all LegalDocument.doc_id to String.")
    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
