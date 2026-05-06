# Hướng dẫn nạp dữ liệu (Ingestion Guide)

Tài liệu này hướng dẫn cách đưa dữ liệu đã cào vào hệ thống RAG (Qdrant, Neo4j, OpenSearch).

## 1. Nạp dữ liệu qua Terminal (Dành cho kỹ thuật)

Đây là cách nhanh nhất và ổn định nhất để nạp dữ liệu lớn.

### Nạp dữ liệu bổ sung (Addition Mode)
Nếu bạn vừa cào dữ liệu với prefix `addition_` và muốn thêm chúng vào hệ thống hiện có (không xóa dữ liệu cũ):

```bash
python scripts/ingest_data.py --prefix "addition_" --mode addition
```

### Nạp toàn bộ dữ liệu (Full Mode)
Nếu bạn muốn xóa trắng các index và nạp lại từ đầu (thường dùng cho lần đầu setup hoặc khi muốn làm sạch dữ liệu):

```bash
python scripts/ingest_data.py --mode full
```

---

## 2. Nạp dữ liệu qua Giao diện Web / API

Nếu ứng dụng web đang chạy, bạn có thể kích hoạt việc nạp dữ liệu thông qua các API endpoint.

### Sử dụng Swagger UI
Truy cập: `http://localhost:8000/docs`

1.  Tìm endpoint `POST /ingest/full`.
2.  Nhấn **Try it out**.
3.  Nhập thông tin JSON:
    *   **Nạp bổ sung:**
        ```json
        {
          "prefix": "addition_",
          "recreate": false
        }
        ```
    *   **Nạp mới hoàn toàn:**
        ```json
        {
          "prefix": "",
          "recreate": true
        }
        ```
4.  Nhấn **Execute**.

### Sử dụng lệnh `curl`
```bash
curl -X 'POST' \
  'http://localhost:8000/ingest/full' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "prefix": "addition_",
  "recreate": false
}'
```

---

## 3. Cơ chế xử lý Graph & Quan hệ

Khi bạn chạy lệnh nạp (dù qua Terminal hay Web), hệ thống sẽ thực hiện các bước sau:
1.  **Chunking:** Chia nhỏ văn bản thành các Điều/Khoản.
2.  **Embedding:** Chuyển đổi văn bản thành Vector và lưu vào Qdrant.
3.  **Relation Extraction:** Trích xuất các liên kết luật pháp (ví dụ: Luật này thay thế luật kia).
4.  **Graph Resolution:** Hệ thống tự động chạy hàm `resolve_all_relations()`. Hàm này sẽ quét toàn bộ database để kết nối các văn bản mới với các văn bản cũ, giúp "xây dựng" bản đồ tri thức (Graph) mà không cần nạp lại toàn bộ.

---

## 4. Nạp bù nội dung thiếu (Backfill Content)

Sử dụng quy trình này khi bạn đã có Metadata nhưng nội dung (`content_html`) của văn bản bị thiếu hoặc quá ngắn (ví dụ: < 500 ký tự).

### Bước 1: Tìm các văn bản bị thiếu
Chạy script để quét bộ dataset hiện tại và xác định danh sách cần nạp bù. Danh sách sẽ được lưu tại `data/raw/backfill_targets.json`.

```bash
python scripts/find_missing_content.py
```

### Bước 2: Chạy nạp bù nội dung
Script này sẽ dùng Số hiệu văn bản để tìm kiếm trên Thư Viện Pháp Luật và chỉ cào duy nhất phần nội dung HTML để cập nhật vào file Parquet, giữ nguyên Metadata cũ của bạn.

*   **Chạy thử nghiệm (2 bản ghi):**
    ```bash
    python scripts/backfill_content.py --limit 2
    ```
*   **Chạy toàn bộ:**
    ```bash
    python scripts/backfill_content.py
    ```

> [!NOTE]
> Hệ thống sẽ tự động tạo bản sao lưu `content.parquet.bak` trước khi ghi đè dữ liệu mới.

---
*Tài liệu được cập nhật ngày 04/05/2026 bởi Antigravity.*

