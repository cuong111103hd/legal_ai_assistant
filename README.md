# 🇻🇳 Vietnamese Legal AI Assistant (GraphRAG + Hybrid Search)

Hệ thống trợ lý ảo hỗ trợ tra cứu và phân tích văn bản pháp luật Việt Nam, sử dụng kiến trúc RAG nâng cao kết hợp giữa **Vector Search** (Qdrant), **Full-text Search** (Postgres) và **Knowledge Graph** (Neo4j).

---

## 🚀 Hướng dẫn cài đặt (Dành cho người mới)

### 1. Khởi tạo môi trường Python
Yêu cầu: Python 3.10 trở lên.

```bash
# Tạo môi trường ảo
python3 -m venv venv

# Kích hoạt môi trường ảo
source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt
```

### 2. Khởi động các Database (Docker)
Nếu bạn phát triển (Develop) và muốn chạy Backend trực tiếp trên máy thay vì trong Docker, bạn chỉ cần chạy các container chứa Database:

```bash
# Chạy Postgres, Qdrant và Neo4j ở chế độ chạy ngầm
docker compose up -d postgres qdrant neo4j
```

### 3. Cấu hình biến môi trường
Sao chép file `.env.example` thành `.env` và cập nhật các thông số (đặc biệt là `OPENAI_API_KEY` nếu bạn dùng GPT):
```bash
cp .env.example .env
```

---

## 📂 Quy trình chuẩn bị dữ liệu (Bắt buộc)

Hệ thống sử dụng cơ chế nạp dữ liệu cục bộ để đảm bảo tốc độ. Hãy thực hiện theo thứ tự 3 bước sau:

### Bước 1: Khởi động Server Backend
```bash
python -m src.main
```

### Bước 2: Tải dữ liệu và Nạp văn bản luật (Dùng API)
Mở một terminal mới và sử dụng các lệnh `curl` sau:

1. **Tải dữ liệu từ HuggingFace về máy:**
   ```bash
   curl -X POST http://localhost:8000/ingest/download-data
   ```

2. **Nạp văn bản luật (Chunking + Embedding):**
   *Nên nạp thử 100 văn bản trước để kiểm tra:*
   ```bash
   curl -X POST "http://localhost:8000/ingest/full?limit=100"
   ```
   *Theo dõi tiến trình có ước tính thời gian (ETA) ngay trên terminal của server.*

3. **Dừng nạp (nếu cần):**
   ```bash
   curl -X POST http://localhost:8000/ingest/stop
   ```

### Bước 3: Nạp quan hệ pháp luật (Dùng Script)
Sau khi nạp văn bản xong, bạn cần nạp các liên kết (Relationships) giữa các văn bản vào Neo4j:

```bash
# Đảm bảo đang ở thư mục gốc và venv đã kích hoạt
export PYTHONPATH=.
python scripts/ingest_relationships.py
```

---

## 🎨 Khởi chạy Giao diện (Frontend)

Hệ thống giao diện được viết bằng React/Vite.

```bash
cd frontend
npm install
npm run dev
```
Truy cập: `http://localhost:5173`

---

## 🛠 Kiến trúc kỹ thuật
- **Hybrid Retriever**: Kết hợp Dense Vector (Qdrant) và BM25 (Postgres).
- **Graph Expansion**: Tự động mở rộng ngữ cảnh dựa trên các văn bản liên quan tìm thấy trong Neo4j.
- **Verification Loop**: Tự động kiểm chứng câu trả lời với văn bản gốc để chống ảo giác (Hallucination).
- **Rich Visualization**: Terminal hiển thị tiến trình nạp dữ liệu chuyên nghiệp.

---

## 📞 Hỗ trợ
Nếu gặp lỗi trong quá trình cài đặt, hãy kiểm tra các cổng (Ports) sau có bị chiếm dụng không:
- `8000` (Backend)
- `5173` (Frontend)
- `5432` (Postgres)
- `6333` (Qdrant)
- `7474/7687` (Neo4j)
