import os
import asyncio
from src.config import settings
from src.main import _db, _retriever, _generator, lifespan
from src.models import ChatRequest, ContractReviewRequest
from fastapi import FastAPI

# Force in-memory Qdrant and small batch size for fast testing
os.environ["QDRANT_IN_MEMORY"] = "true"
os.environ["EMBEDDING_BATCH_SIZE"] = "2"
settings.QDRANT_IN_MEMORY = True
settings.EMBEDDING_BATCH_SIZE = 2
# Do not actually call external API unless GROQ_API_KEY is properly set, but let's test ingestion + retrieval first.

async def test_pipeline():
    print("🚀 Starting smoke test...")
    app = FastAPI()
    
    # Run ingestion first with a tiny limit
    print("▶️ Testing ingestion (limit=5)...")
    from src.ingestion import run_ingestion
    status = run_ingestion(limit=5)
    print("✅ Ingestion status:", status.state, "- docs:", status.processed_documents, "chunks:", status.total_chunks)
    
    if status.state == "failed":
        print("❌ Ingestion failed!")
        return

    async with lifespan(app):
        # By this time, _retriever and _generator should be initialized.
        from src.main import _retriever, _generator
        
        print("▶️ Testing retrieval...")
        query = "bảo hiểm"
        results = _retriever.search(query=query, top_k=2)
        print("✅ Retrieved chunks:", len(results))
        for r in results:
            print("   -", r.chunk.document_id, r.chunk.law_name, r.score, r.source)
        
        print("▶️ Testing evidence pack...")
        pack = _retriever.build_evidence_pack(results)
        print("✅ Citations:", len(pack.citations))

        if settings.GROQ_API_KEY and not settings.GROQ_API_KEY.startswith("gsk_..."):
            print("▶️ Testing generator (sync chat)...")
            ans = _generator.answer_question("bảo hiểm là gì?", top_k=2)
            print("✅ LLM Answer:", ans.answer[:100], "...")
        else:
            print("⚠️ Skipping LLM generation test (GROQ_API_KEY not set).")

if __name__ == "__main__":
    asyncio.run(test_pipeline())
