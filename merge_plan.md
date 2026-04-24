# 📊 Kế hoạch Hợp nhất: So sánh & Lựa chọn Triển khai

Dưới đây là bảng so sánh chi tiết các phương pháp triển khai giữa hai dự án cho cùng một mục đích. Bảng này sẽ giúp bạn đưa ra quyết định giữ lại hoặc loại bỏ thành phần nào khi tiến hành merge dự án `reference_nam` vào dự án chính.

---

## 1. Tải Dữ Liệu (HuggingFace Download)

| Tiêu chí | Dự án Chính (Hiện tại) | Dự án Reference | Khuyến nghị cho bản Merge |
| :--- | :--- | :--- | :--- |
| **Cơ chế tải** | Streaming trực tiếp (`load_dataset`) | Streaming cho Content/Meta + Tải trực tiếp file `.parquet` (cho Relation) và lưu Cache | **Giữ cách của Reference**. Việc lưu cache file quan hệ giúp tránh phải tải lại file nặng. Streaming content/meta thì giữ nguyên. |
| **Xử lý nội dung** | Giữ nguyên định dạng HTML để hiển thị đẹp trên UI | Dùng `BeautifulSoup` để loại bỏ hoàn toàn HTML, đưa về Plain Text | **Nửa nọ nửa kia**. Lưu HTML vào Postgres để hiển thị UI, nhưng dùng Text thô (đã qua BeautifulSoup) để Chunking và Đưa cho AI. |

---

## 2. Nạp Dữ Liệu & Chia Nhỏ (Ingestion & Chunking)

| Tiêu chí | Dự án Chính (Hiện tại) | Dự án Reference | Khuyến nghị cho bản Merge |
| :--- | :--- | :--- | :--- |
| **Quy trình Ingest** | Chạy 1 luồng: Lọc -> Tải -> Lưu Postgres -> Chunk -> Qdrant -> Build BM25 | Chạy đa luồng (Pipeline): Tách biệt Nạp Nội dung và Nạp Quan hệ (Neo4j) | **Giữ cách của Reference (Tách biệt)**. Nạp nội dung trước, nạp quan hệ sau. Điều này giúp tránh lỗi đứt gãy hệ thống. |
| **Xử lý Bộ lọc** | Lọc chặt ngay từ đầu (2015+, Luật/Bộ luật) | Lọc lỏng hơn, thu thập diện rộng | **Giữ cách của Dự án Chính**. Trong giới hạn phần cứng hiện tại, việc lọc dữ liệu rác ngay từ đầu là cần thiết. |
| **Cơ sở dữ liệu** | Postgres + Qdrant + File BM25 cục bộ | Postgres + Qdrant + OpenSearch + Neo4j | **Mở rộng**. Nâng cấp file BM25 lên ElasticSearch/OpenSearch (nếu server đủ mạnh) và bổ sung Neo4j để lưu quan hệ. |

---

## 3. Quy trình Truy vấn (Retrieval)

| Tiêu chí | Dự án Chính (Hiện tại) | Dự án Reference | Khuyến nghị cho bản Merge |
| :--- | :--- | :--- | :--- |
| **Cơ chế Search** | Hybrid (Vector Qdrant + Sparse BM25 cục bộ) + RRF | Hybrid (Vector + OpenSearch) + **GraphRAG (Neo4j)** | **Tích hợp GraphRAG**. Tiếp tục dùng Vector + Sparse, nhưng dùng Neo4j để tìm thêm các văn bản Sửa đổi/Bổ sung/Hướng dẫn liên quan. |
| **Ngữ cảnh (Context)** | Cắt lấy các Điều lân cận (Adjacent) | Mở rộng qua các cạnh của Graph (Cites, Amended_by) | **Kết hợp**. Vừa lấy Điều lân cận để có ngữ cảnh dọc, vừa dùng Graph để có ngữ cảnh ngang (các bộ luật khác). |

---

## 4. Suy luận & Tác tử (Agents & Reasoning)

| Tiêu chí | Dự án Chính (Hiện tại) | Dự án Reference | Khuyến nghị cho bản Merge |
| :--- | :--- | :--- | :--- |
| **Xử lý câu hỏi** | LLM đọc và tự hiểu | **Planner**: Chuyển viết tắt (BLHS), tìm đồng nghĩa, nhận diện phủ định ("không được") trước khi search. | **ÁP DỤNG NGAY PLANNER**. Đây là tính năng tốn ít tài nguyên nhất nhưng mang lại hiệu quả tìm kiếm đột phá. |
| **Độ tin cậy** | Chỉ dựa vào Prompt mặc định | **Verifier**: Dùng Agent thứ 2 kiểm tra lại kết quả của Generator xem có chém gió không. | **Tích hợp Verifier**. Rất cần thiết cho lĩnh vực pháp lý để đảm bảo "Zero Hallucination". |
| **Cấu trúc Code** | Dồn vào 1 vài file lớn | Chia theo Packages (`planner`, `generator`, `verifier`) | **Cấu trúc lại theo Packages**. Giúp dễ debug và mở rộng về sau. |

---

## 🚀 Lộ trình Merge Đề xuất

Để việc merge không làm hỏng dự án đang chạy ổn định, chúng ta nên đi theo 3 Giai đoạn:

1.  **Giai đoạn 1 (Dễ nhất - Đột phá ngay): Tích hợp Agent Planner**
    *   Sử dụng bộ từ điển viết tắt và logic của Planner từ Reference sang.
    *   Xử lý câu hỏi người dùng trước khi gọi Hybrid Search hiện tại.
2.  **Giai đoạn 2 (Dữ liệu nền tảng): Nâng cấp Ingestion & Neo4j**
    *   Tích hợp Neo4j vào `docker-compose`.
    *   Copy script tải `relationships.parquet` và script nạp Neo4j (`ingest_relationships.py`).
    *   Thay đổi cách xử lý Text: Lưu HTML cho UI nhưng đẩy Plain Text cho AI.
3.  **Giai đoạn 3 (Nâng cao): GraphRAG & Verifier**
    *   Chỉnh sửa Retriever hiện tại để kết nối với Neo4j (Graph Augmented Search).
    *   Thêm Verifier Agent để kiểm chứng kết quả cuối cùng.
