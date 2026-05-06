import sys
import os
import uuid
import numpy as np

# Thêm thư mục gốc vào path để import các module trong src/
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.retriever import HybridRetriever
from src.config import settings
from qdrant_client import QdrantClient

import json

def print_result_full_metadata(results):
    """In toàn bộ metadata và điểm số cho mỗi kết quả."""
    for i, res in enumerate(results):
        print(f"\n{'='*15} RESULT {i+1} {'='*15}")
        print(f"SCORE: {res.score:.6f}")
        
        # Tạo dictionary chứa metadata từ object LegalChunk
        metadata = {
            "chunk_id": res.chunk.chunk_id,
            "document_id": res.chunk.document_id,
            "document_number": res.chunk.document_number,
            "law_name": res.chunk.law_name,
            "article_id": res.chunk.article_id,
            "doc_type": res.chunk.doc_type,
            "validity_status": res.chunk.validity_status,
            "chunk_index": res.chunk.chunk_index,
        }
        
        print("METADATA:")
        print(json.dumps(metadata, indent=2, ensure_ascii=False))
        print(f"{'-'*40}")

def cosine_similarity(v1, v2):
    v1 = np.array(v1)
    v2 = np.array(v2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def main():
    # Khởi tạo retriever (để lấy model embedding)
    print("Loading embedding model and connecting to Qdrant...")
    try:
        retriever = HybridRetriever()
        client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    except Exception as e:
        print(f"Initialisation error: {e}")
        return
    
    while True:
        print("\n" + "="*50)
        print("   VIETNAMESE LEGAL VECTOR SEARCH TESTER")
        print("="*50)
        print("1. Search Top K (Pure Vector)")
        print("2. Compare Query vs Point ID")
        print("0. Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == '0':
            print("Bye!")
            break
            
        if choice == '1':
            query = input("Query: ").strip()
            if not query: continue
            
            k_input = input("K (default 10): ").strip()
            k = int(k_input) if k_input else 10
            
            # Thực hiện search dense thuần túy thông qua retriever
            try:
                results = retriever.search_dense(query, top_k=k)
                
                if not results:
                    print("No results found.")
                else:
                    print_result_full_metadata(results)
            except Exception as e:
                print(f"Search error: {e}")
                
        elif choice == '2':
            query = input("Query: ").strip()
            if not query: continue
            
            point_id_str = input("Point ID (UUID or int): ").strip()
            if not point_id_str: continue
            
            try:
                # Encode query sang vector
                query_vector = retriever._encode_query(query)
                
                # Xử lý Point ID
                target_id = point_id_str
                # Kiểm tra nếu là số nguyên
                if point_id_str.isdigit():
                    target_id = int(point_id_str)
                else:
                    # Kiểm tra nếu là UUID hợp lệ
                    try:
                        uuid.UUID(point_id_str)
                    except ValueError:
                        pass # Giữ nguyên string nếu không phải UUID
                
                points = client.retrieve(
                    collection_name=settings.QDRANT_COLLECTION,
                    ids=[target_id],
                    with_vectors=True,
                    with_payload=True
                )
                
                if not points:
                    print(f"Error: Point '{point_id_str}' not found in collection '{settings.QDRANT_COLLECTION}'.")
                    continue
                
                point_data = points[0]
                point_vector = point_data.vector
                payload = point_data.payload or {}
                
                # Tính độ tương đồng
                score = cosine_similarity(query_vector, point_vector)
                
                print("\n" + "-"*40)
                print(f"QUERY: {query}")
                print(f"COSINE SIMILARITY: {score:.6f}")
                print("-" * 15 + " POINT METADATA " + "-" * 15)
                # Loại bỏ content khỏi payload để chỉ in metadata
                meta_to_print = {k: v for k, v in payload.items() if k != 'content'}
                print(json.dumps(meta_to_print, indent=2, ensure_ascii=False))
                print("-" * 40)
                
            except Exception as e:
                print(f"Comparison error: {e}")
        else:
            print("Invalid choice. Please enter 1, 2 or 0.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
