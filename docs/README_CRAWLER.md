# Hướng dẫn sử dụng Vietnamese Legal Crawler

Tài liệu này hướng dẫn cách sử dụng công cụ cào dữ liệu pháp luật từ `thuvienphapluat.vn` và cách nạp dữ liệu vào hệ thống RAG.

## 1. Cách sử dụng Crawler

Sử dụng script `scripts/crawl_thuvienphapluat.py` để tìm kiếm và tải văn bản.

### Lệnh cơ bản:
```bash
python scripts/crawl_thuvienphapluat.py --keywords "SỐ_HIỆU_1" "SỐ_HIỆU_2" --prefix "TÊN_PREFIX_"
```

### Các tham số:
*   `--keywords`: Danh sách số hiệu văn bản (cách nhau bởi dấu cách). Ví dụ: `88/2025/QH15`.
*   `--prefix`: Tiền tố cho file kết quả.
    *   Dùng `test_` để thử nghiệm.
    *   Dùng `addition_` để cào dữ liệu bổ sung (không muốn ghi đè vào kho chính).
    *   Để trống `""` nếu muốn lưu vào kho dữ liệu chính (`metadata.parquet` và `content.parquet`).

## 2. Cơ chế lưu trữ của Crawler

Crawler hoạt động theo cơ chế **Cộng dồn (Incremental)**:
*   Nếu file parquet đã tồn tại, crawler sẽ đọc dữ liệu cũ và gộp với dữ liệu mới cào được.
*   Hệ thống tự động xóa trùng lặp dựa trên `id` văn bản, đảm bảo mỗi văn bản chỉ xuất hiện một lần duy nhất.

## 3. Nạp dữ liệu vào hệ thống (Ingestion)

Sau khi cào xong với prefix `addition_`, bạn cần nạp chúng vào cơ sở dữ liệu Vector (Qdrant) và Graph (Neo4j).

### Cách nạp dữ liệu bổ sung:
Hệ thống đã được cập nhật để hỗ trợ nạp bổ sung mà không xóa dữ liệu cũ.

```python
# Ví dụ gọi từ code
from src.ingestion import run_full_ingestion
await run_full_ingestion(prefix="addition_", recreate=False)
```

**Lưu ý:**
*   `recreate=False`: Đảm bảo Qdrant và OpenSearch không bị xóa trắng mà chỉ thêm (upsert) các bản ghi mới.
*   `resolve_all_relations()`: Sẽ được chạy lại để kết nối các văn bản mới vào Graph.

## 5. Chiến lược Chunking & Tối ưu hóa tìm kiếm (OpenSearch)

Hệ thống RAG đã được tối ưu hóa đặc biệt để xử lý các truy vấn pháp lý phức tạp (như "Điều 20 Bộ luật Dân sự"):

### Chiến lược Shingles (Bigrams)
OpenSearch sử dụng bộ lọc `shingle_filter` để lưu trữ các cụm từ liền kề (2-3 từ).
*   **Mục tiêu:** Giúp phân biệt chính xác giữa "Điều 20, Khoản 1" và "Khoản 20, Điều 1".
*   **Kết quả:** Các cụm từ như "điều 20" sẽ được khớp chính xác hơn so với việc chỉ đếm các từ đơn lẻ.

### Tối ưu trọng số (Boosting)
Trong file `src/database_opensearch.py`, trọng số tìm kiếm được cấu hình để ưu tiên tên văn bản:
*   `law_name^10`: Tên luật có trọng số cao nhất (gấp 10 lần) để đảm bảo khi tìm "dân sự", các văn bản thuộc Bộ luật Dân sự luôn đứng đầu.
*   `article_id^3`: Tiêu đề Điều/Khoản có trọng số cao thứ hai.

---

