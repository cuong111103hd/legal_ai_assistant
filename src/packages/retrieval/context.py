import logging
from typing import List, Optional
from src.packages.graph.legal_graph import LegalGraphClient
from src.models import SearchResult, LegalChunk, SearchSource

logger = logging.getLogger(__name__)

class ContextInjector:
    """
    Enhances search results with additional context from the graph database
    (e.g., related guided documents, legal basis).
    """

    def __init__(self, settings, graph_client: Optional[LegalGraphClient] = None):
        self.settings = settings
        self.graph_client = graph_client or LegalGraphClient()

    async def inject_graph_context(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        For each search result, find related documents in the graph and 
        inject them as additional context.
        """
        if not self.graph_client:
            return results

        logger.info("Injecting graph-based context into search results...")
        
        seen_doc_ids = {sr.chunk.document_id for sr in results}
        enriched_results = list(results)
        
        for sr in results:
            doc_id = sr.chunk.document_id
            # Fetch related documents from graph
            # We specifically look for guided documents (Văn bản hướng dẫn) or bases
            related_docs = await self.graph_client.get_related_documents(
                doc_id, 
                rel_types=["VAN_BAN_HUONG_DAN", "CAN_CU_PHAP_LY"]
            )
            
            for rel in related_docs:
                rel_doc_id = rel["document_id"]
                if rel_doc_id not in seen_doc_ids:
                    seen_doc_ids.add(rel_doc_id)
                    
                    # Create a "pseudo-chunk" for the related document to provide context
                    # Note: In a full implementation, we might want to fetch actual chunks of the related doc
                    context_chunk = LegalChunk(
                        chunk_id=f"graph_{rel_doc_id}",
                        document_id=rel_doc_id,
                        law_name=rel["title"],
                        document_number=rel["document_number"],
                        doc_type=rel["doc_type"],
                        content=f"[BỐI CẢNH PHÁP LÝ] Văn bản này có liên quan: {rel['title']} ({rel['document_number']}). "
                                f"Mối quan hệ: {rel['relationship_type']}.",
                        validity_status="N/A"
                    )
                    
                    enriched_results.append(
                        SearchResult(
                            chunk=context_chunk,
                            score=sr.score * 0.8, # Lower score for indirect context
                            source=SearchSource.HYBRID
                        )
                    )
                    
        logger.info(f"Context injection added {len(enriched_results) - len(results)} related documents.")
        return enriched_results
