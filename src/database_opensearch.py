"""
OpenSearch manager for sparse/lexical retrieval.
Supports multi-match querying with boosting on metadata fields.
"""

import logging
from typing import Optional

from opensearchpy import OpenSearch, helpers

from .config import settings
from .models import LegalChunk

logger = logging.getLogger(__name__)

class OpenSearchManager:
    def __init__(self):
        self.host = settings.OPENSEARCH_HOST
        self.port = settings.OPENSEARCH_PORT
        self.index_name = settings.OPENSEARCH_INDEX
        self.client = OpenSearch(
            hosts=[{"host": self.host, "port": self.port}],
            http_compress=True,
        )

    def ping(self) -> bool:
        """Check if OpenSearch is reachable."""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"OpenSearch ping failed: {e}")
            return False

    def create_index(self, recreate: bool = False) -> None:
        """Create the OpenSearch index with Vietnamese analyzer and appropriate mapping."""
        if recreate and self.client.indices.exists(index=self.index_name):
            self.client.indices.delete(index=self.index_name)
            logger.info(f"Deleted existing index: {self.index_name}")

        if not self.client.indices.exists(index=self.index_name):
            mapping = {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "analysis": {
                        "filter": {
                            "shingle_filter": {
                                "type": "shingle",
                                "min_shingle_size": 2,
                                "max_shingle_size": 3,
                                "output_unigrams": True
                            }
                        },
                        "analyzer": {
                            "vietnamese_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": ["lowercase", "shingle_filter"]
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "chunk_id": {"type": "keyword"},
                        "document_id": {"type": "keyword"},
                        "law_name": {
                            "type": "text",
                            "analyzer": "vietnamese_analyzer"
                        },
                        "article_id": {
                            "type": "text",
                            "analyzer": "vietnamese_analyzer"
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "vietnamese_analyzer"
                        },
                        "validity_status": {"type": "keyword"},
                        "doc_type": {"type": "keyword"},
                        "document_number": {
                            "type": "text",
                            "analyzer": "vietnamese_analyzer"
                        },
                        "chunk_index": {"type": "integer"}
                    }
                }
            }
            self.client.indices.create(index=self.index_name, body=mapping)
            logger.info(f"Created OpenSearch index: {self.index_name}")

    def upsert_batch(self, chunks: list[LegalChunk]) -> None:
        """Bulk index a batch of LegalChunks into OpenSearch."""
        if not chunks:
            return

        actions = []
        for chunk in chunks:
            action = {
                "_op_type": "index",
                "_index": self.index_name,
                "_id": chunk.chunk_id, # Use chunk_id as the document ID in OpenSearch
                "_source": chunk.model_dump()
            }
            actions.append(action)

        try:
            success, failed = helpers.bulk(self.client, actions, refresh=True)
            logger.info(f"OpenSearch: Indexed {success} chunks. Failed: {failed}")
        except Exception as e:
            logger.error(f"OpenSearch bulk indexing error: {e}")

    def search(self, query: str, top_k: int = 10) -> list[tuple[LegalChunk, float]]:
        """
        Search OpenSearch using multi-match with field boosting.
        Returns a list of (LegalChunk, score) tuples.
        """
        if not query.strip():
            return []

        search_body = {
            "size": top_k,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": [
                        "article_id^3",
                        "document_number^2",
                        "law_name^10",
                        "content"
                    ],
                    "type": "cross_fields",
                    "operator": "or"
                }
            }
        }

        try:
            response = self.client.search(index=self.index_name, body=search_body)
            hits = response["hits"]["hits"]
            
            # Map back to (LegalChunk, score)
            results = []
            for hit in hits:
                chunk_data = hit["_source"]
                # In case some fields are missing from older dumps, handle them gracefully if needed
                chunk = LegalChunk(**chunk_data)
                results.append((chunk, float(hit["_score"])))
                
            return results
        except Exception as e:
            logger.error(f"OpenSearch search error: {e}")
            return []
