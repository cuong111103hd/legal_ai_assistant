# 📜 Báo cáo Kiến trúc Hệ thống LegalTech - Version 1.0

## 1. System Architecture (Kiến trúc Hệ thống)

Hệ thống hiện tại được thiết kế theo mô hình **Hybrid RAG (Retrieval-Augmented Generation)**, kết hợp giữa tìm kiếm ngữ nghĩa (Semantic Search), tìm kiếm từ khóa (Keyword Search) và mở rộng tri thức qua đồ thị (Graph Expansion).

### Sơ đồ Luồng Dữ liệu (Data Flow)
1.  **Ingestion Flow**:
    -   Dữ liệu từ Parquet -> **PostgreSQL** (Lưu trữ toàn văn & Metadata).
    -   Dữ liệu -> Chunking (Article level) -> **Qdrant** (Lưu vector embeddings).
    -   Dữ liệu -> Relationship Extraction -> **Neo4j** (Lưu liên kết giữa các văn bản).
2.  **Retrieval Flow**:
    -   **User Query** -> **LegalQueryPlanner**: Chuẩn hóa, mở rộng từ viết tắt/đồng nghĩa.
    -   **Hybrid Search**:
        -   Qdrant (Dense Search).
        -   BM25 Index (Sparse Search).
        -   Kết hợp bằng thuật toán **Reciprocal Rank Fusion (RRF)**.
    -   **Graph Expansion**: Từ kết quả top-k, truy vấn Neo4j để tìm các văn bản liên quan (RELATES_TO).
    -   **Context Injection**: Lấy thêm các đoạn (chunks) liền kề trong cùng văn bản để đảm bảo ngữ cảnh.
3.  **Generation Flow**:
    -   **EvidencePack**: Tập hợp các trích dẫn (citations) và nội dung.
    -   **LLM Generator**: Sử dụng Groq/OpenAI để tạo câu trả lời dựa trên EvidencePack.
    -   **LegalVerifier**: Hậu kiểm để loại bỏ ảo giác (hallucination).

---

## 2. Data Schema hiện tại

### Neo4j (Graph Database)
Hiện tại, schema trong Neo4j đang ở mức độ tối giản (MVP):
-   **Nodes**: 
    -   Label: `LegalDocument`
    -   Properties: `doc_id` (Unique)
-   **Relationships**: 
    -   Type: `RELATES_TO` (Mối quan hệ ngang hàng giữa hai văn bản pháp luật).
    -   Property: `type` (Mô tả loại quan hệ như "căn cứ", "dẫn chiếu").

### PostgreSQL (Relational Database)
-   **Table `legal_documents`**: Lưu trữ toàn văn để tra cứu và hiển thị.
    -   `id`, `title`, `content_html`, `clean_text`, `doc_type`, `document_number`, `validity_status`.
-   **Table `chat_sessions` & `chat_messages`**: Lưu lịch sử hội thoại.
    -   `session_id`, `role`, `content`, `citations_json` (Lưu các trích dẫn đã sử dụng).

---

## 3. Logic Flow (Luồng xử lý truy vấn)

1.  **Tiếp nhận & Lập kế hoạch (Planning)**: `LegalQueryPlanner` phân tích câu hỏi, nhận diện các thực thể pháp lý (Điều, Luật, Nghị định) và mở rộng từ vựng.
2.  **Truy xuất (Retrieval)**: 
    -   Tìm kiếm vector trên Qdrant để lấy các đoạn văn bản có ý nghĩa gần nhất.
    -   Tìm kiếm từ khóa (BM25) để bắt các thuật ngữ chuyên ngành chính xác.
    -   Mở rộng đồ thị: Nếu tìm thấy văn bản A, hệ thống hỏi Neo4j: "Văn bản A liên quan đến văn bản nào khác?". Nếu có văn bản B, hệ thống nạp thêm các đoạn đầu của văn bản B vào ngữ cảnh.
3.  **Tổng hợp (Synthesis)**: Đưa toàn bộ context vào prompt theo cấu trúc `EvidencePack`. LLM được yêu cầu chỉ trả lời dựa trên dữ liệu được cung cấp, ghi rõ số thứ tự trích dẫn `[1], [2]`.
4.  **Kiểm chứng (Verification)**: Một sub-agent sẽ đối chiếu câu trả lời của LLM với EvidencePack để đảm bảo không có thông tin sai lệch.

---

## 4. Gap Analysis (Phân tích khoảng trống)

Hiện tại, hệ thống MVP vẫn còn các hạn chế lớn cần giải quyết để tiến tới "GraphRAG nâng cao":

-   **Thiếu Granularity (Độ chi tiết)**: 
    -   Chunking mới chỉ dừng ở cấp độ **Điều (Article)**. Trong pháp luật, một Điều có thể rất dài và chứa nhiều **Khoản (Clause)**, **Điểm (Point)** với nội dung khác biệt hoàn toàn.
    -   Neo4j chưa có node cho Điều/Khoản/Điểm, dẫn đến không thể truy vấn quan hệ phân cấp.
-   **GraphRAG chưa tối ưu**:
    -   Quan hệ trong Neo4j mới chỉ là Document-to-Document. 
    -   Chưa xử lý được logic: "Điều A của Luật X dẫn chiếu đến Điều B của Luật Y". Hiện tại hệ thống chỉ biết "Luật X liên quan Luật Y".
-   **Logging suy luận**: 
    -   Chưa lưu lại "Thought process" (quy trình suy luận) của Agent vào PostgreSQL để phục vụ giám sát và tinh chỉnh.
-   **Tích hợp Ingestion**: 
    -   Quá trình nạp dữ liệu vào Neo4j đang tách biệt với pipeline chính trong `ingestion.py`.

---

## 5. Technical Debt (Nợ kỹ thuật & Cần Refactor)

1.  **Refactor `chunk_html_by_article`**: Cần nâng cấp thành `chunk_html_hierarchical` để bóc tách được Khoản và Điểm.
2.  **Neo4j Schema Design**: Cần triển khai schema mới: `(Document)-[:HAS_ARTICLE]->(Article)-[:HAS_CLAUSE]->(Clause)`.
3.  **Relationship Extraction**: Cần một module NLP (hoặc dùng LLM) để trích xuất các mối quan hệ dẫn chiếu cụ thể (ví dụ: "theo quy định tại Khoản 2 Điều này...") ngay trong quá trình ingestion.
4.  **PostgreSQL Logging**: Bổ sung bảng `agent_thoughts` để lưu log từ `planner.py` và `generator.py`.
5.  **Unified Ingestion**: Hợp nhất việc nạp vào Qdrant, Neo4j và Postgres vào một pipeline duy nhất để đảm bảo tính nhất quán của ID.
