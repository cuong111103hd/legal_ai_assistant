# Quy trình nạp dữ liệu (Ingestion Pipeline)

Hệ thống sử dụng cơ chế nạp dữ liệu **Local-first** (Ưu tiên dữ liệu cục bộ) để đảm bảo tốc độ và tính ổn định cao nhất. Dữ liệu sẽ được tải từ HuggingFace về máy một lần duy nhất, sau đó việc nạp vào Database sẽ diễn ra hoàn toàn offline.

---

## 1. Các bước thực hiện

### Bước 1: Tải dữ liệu về máy (Download Data)
Trước khi nạp dữ liệu, bạn cần tải các file `.parquet` từ HuggingFace.

*   **URL**: `POST /ingest/download-data`
*   **Lệnh Curl**:
    ```bash
    curl -X POST http://localhost:8000/ingest/download-data
    ```
*   **Kết quả**: Các file sẽ được lưu vào thư mục `data/raw/` trong project. Bạn có thể theo dõi tiến trình tải (%) ngay trên Terminal của server.

### Bước 2: Nạp dữ liệu vào Database (Ingest)
Sau khi đã có file cục bộ, bạn có thể bắt đầu nạp dữ liệu vào PostgreSQL và Qdrant.

*   **Nạp toàn bộ (Full Ingest)**:
    ```bash
    curl -X POST "http://localhost:8000/ingest/full"
    ```
*   **Nạp giới hạn (Dùng để test nhanh)**:
    ```bash
    curl -X POST "http://localhost:8000/ingest/full?limit=100"
    ```
*   **Dừng nạp khẩn cấp**: Nếu đang nạp mà muốn dừng lại ngay lập tức:
    ```bash
    curl -X POST "http://localhost:8000/ingest/stop"
    ```

---

## 2. Các phương thức nạp khác

### Nạp theo số hiệu văn bản (Targeted Ingest)
Nếu bạn chỉ muốn cập nhật một vài văn bản cụ thể dựa trên `so_ky_hieu`:

*   **URL**: `POST /ingest/by-numbers`
*   **Body**:
    ```json
    {
      "doc_numbers": ["123/2020/NĐ-CP", "456/2021/TT-BTC"]
    }
    ```

### Kiểm tra trạng thái nạp
Bạn có thể kiểm tra xem hệ thống đã nạp được bao nhiêu văn bản/phân đoạn:

*   **URL**: `GET /ingest/status`

---

## 3. Theo dõi qua Terminal (Giao diện Rich)
Hệ thống tích hợp thư viện `rich` để hiển thị trực quan các thông tin sau:
- **Thanh tiến trình Download**: Theo dõi dung lượng và tốc độ tải.
- **Thanh tiến trình Chunking**: Theo dõi quá trình cắt nhỏ văn bản.
- **Thanh tiến trình Embedding**: Theo dõi quá trình tạo vector (kèm theo ước tính thời gian còn lại - ETA).
- **Bảng tổng kết (Summary)**: Hiển thị tổng số văn bản và phân đoạn đã nạp khi kết thúc.

---

## 4. Lưu ý quan trọng
- Khi nạp dữ liệu lần đầu, hãy đảm bảo các Database (Postgres, Qdrant, Neo4j) đang hoạt động.
- Quá trình **Full Ingest** sẽ xóa (recreate) collection cũ trong Qdrant để đảm bảo dữ liệu mới nhất.
- Sau khi nạp xong, hệ thống sẽ tự động khởi động lại bộ máy tìm kiếm (Retriever) để cập nhật dữ liệu mới.
