import logging
import asyncio
from typing import List, Optional, Any
from opensearchpy import AsyncOpenSearch
from src.config import settings
from src.database import QdrantManager
from src.packages.retrieval.embedding import EmbeddingService
from src.packages.retrieval.context import ContextInjector
from src.models import SearchResult, SearchSource, LegalChunk, Citation, EvidencePack
from src.utils.text_processing import (
    extract_article_id,
    extract_clause_id,
    extract_document_number,
)

logger = logging.getLogger(__name__)

class HybridRetriever:
    """
    Advanced hybrid retriever combining:
    1. Dense Search (Qdrant)
    2. Sparse Search (OpenSearch BM25)
    3. Graph-based Context (Neo4j)
    """

    def __init__(self, settings):
        self.settings = settings
        self.embedding_service = EmbeddingService.get_instance()
        self._qdrant = QdrantManager()
        self._opensearch: Optional[AsyncOpenSearch] = None
        self.context_injector = ContextInjector(settings)

    async def _get_opensearch_client(self) -> AsyncOpenSearch:
        """Lazy initialization of OpenSearch client."""
        if not self._opensearch:
            self._opensearch = AsyncOpenSearch(
                hosts=[{'host': self.settings.OPENSEARCH_HOST, 'port': self.settings.OPENSEARCH_PORT}],
                use_ssl=False,
                verify_certs=False,
            )
        return self._opensearch

    async def search_dense(self, query: str, top_k: int = 10, validity_filter: Optional[str] = None) -> List[SearchResult]:
        """Dense vector search using Qdrant."""
        vector = self.embedding_service.encode_query(query)
        return self._qdrant.search_dense(vector, top_k=top_k, validity_filter=validity_filter)

    async def search_sparse(self, query: str, top_k: int = 10) -> List[SearchResult]:
        """Sparse keyword search using OpenSearch BM25."""
        client = await self._get_opensearch_client()
        
        search_body = {
            "size": top_k,
            "query": {
                "match": {
                    "content": query
                }
            }
        }
        
        try:
            response = await client.search(index="legal_documents", body=search_body)
            hits = response['hits']['hits']
            
            results = []
            for hit in hits:
                source = hit['_source']
                chunk = LegalChunk(
                    chunk_id=hit['_id'],
                    document_id=source.get('document_id', ''),
                    law_name=source.get('law_name', ''),
                    content=source.get('content', ''),
                    validity_status=source.get('validity_status', 'Còn hiệu lực')
                )
                results.append(SearchResult(chunk=chunk, score=hit['_score'], source=SearchSource.SPARSE))
            return results
        except Exception as e:
            logger.warning(f"OpenSearch search failed: {e}. Falling back to empty results.")
            return []

    async def search(
        self, 
        query: str, 
        top_k: int = 10, 
        validity_filter: Optional[str] = None,
        use_graph: bool = True
    ) -> List[SearchResult]:
        """
        Execute full hybrid search pipeline with RRF and Graph context.
        """
        logger.info(f"Hybrid search for: {query}")
        
        # 1. Run dense and sparse search in parallel
        dense_task = self.search_dense(query, top_k=top_k, validity_filter=validity_filter)
        sparse_task = self.search_sparse(query, top_k=top_k)
        
        dense_results, sparse_results = await asyncio.gather(dense_task, sparse_task)
        
        # 2. RRF Fusion
        fused_results = self._reciprocal_rank_fusion([dense_results, sparse_results], k=self.settings.RRF_K)
        top_results = fused_results[:top_k]
        
        # 3. Inject graph context if requested
        if use_graph:
            top_results = await self.context_injector.inject_graph_context(top_results)
            
        return top_results

    def _reciprocal_rank_fusion(self, result_lists: List[List[SearchResult]], k: int = 60) -> List[SearchResult]:
        """RRF algorithm to merge ranked lists."""
        scores: dict[str, float] = {}
        chunk_map: dict[str, LegalChunk] = {}

        for results in result_lists:
            for rank, sr in enumerate(results, start=1):
                cid = sr.chunk.chunk_id
                scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
                if cid not in chunk_map:
                    chunk_map[cid] = sr.chunk

        sorted_cids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            SearchResult(chunk=chunk_map[cid], score=score, source=SearchSource.HYBRID)
            for cid, score in sorted_cids
        ]

    @staticmethod
    def build_evidence_pack(results: List[SearchResult]) -> EvidencePack:
        """
        Convert search results into a structured EvidencePack for the LLM.
        """
        citations: List[Citation] = []
        seen: set[str] = set()

        for sr in results:
            chunk = sr.chunk
            article = getattr(chunk, 'article_id', None) or extract_article_id(chunk.content)
            clause = extract_clause_id(chunk.content)
            doc_num = getattr(chunk, 'document_number', None) or extract_document_number(chunk.law_name) or extract_document_number(chunk.content)

            # Deduplicate by article + law_name
            key = f"{article}|{chunk.law_name}"
            if key in seen:
                continue
            seen.add(key)

            # Use first ~500 chars as excerpt
            excerpt = chunk.content[:500].strip()
            if len(chunk.content) > 500:
                excerpt += " …"

            citations.append(
                Citation(
                    article=article or "N/A",
                    clause=clause,
                    law_name=chunk.law_name,
                    document_number=doc_num,
                    document_id=chunk.document_id,
                    excerpt=excerpt,
                )
            )

        return EvidencePack(citations=citations)

    async def close(self):
        """Cleanup clients."""
        if self._opensearch:
            await self._opensearch.close()
        await self._qdrant.close()
