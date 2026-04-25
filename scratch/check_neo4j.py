import asyncio
from src.database_neo4j import Neo4jManager

async def main():
    manager = Neo4jManager()
    await manager.connect()
    
    # 1. Check a few doc_ids in Neo4j
    results = await manager.execute_query("MATCH (n:LegalDocument) RETURN n.doc_id as id LIMIT 5")
    print(f"Neo4j doc_ids: {[r['id'] for r in results]}")
    
    # 2. Check relationship count
    rel_count = await manager.execute_query("MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count")
    print(f"Relationship count: {rel_count[0]['count']}")
    
    await manager.close()

if __name__ == "__main__":
    asyncio.run(main())
