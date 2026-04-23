# ⚖️ Trợ Lý Pháp Luật Việt Nam (Legal AI Assistant)

Chào mừng bạn đến với hệ thống Trợ lý Pháp luật Việt Nam thế hệ mới. Đây là một nền tảng **RAG (Retrieval-Augmented Generation)** cấp độ sản xuất (Production-Grade), được thiết kế chuyên sâu để giải quyết các bài toán tra cứu luật pháp, trả lời câu hỏi tư vấn và rà soát rủi ro hợp đồng dựa trên dữ liệu luật chính thống.

---

## ✨ Tính năng chính (Features)

- **🔍 Hybrid Search & RRF**: Kết hợp tìm kiếm Vector (Semantic) và Từ khóa (Lexical - BM25) giúp tìm kiếm chính xác kể cả khi người dùng không dùng thuật ngữ chuyên môn.
- **📜 Deep-link Citations**: Mọi câu trả lời của AI đều đi kèm trích dẫn Điều/Khoản. Người dùng có thể nhấn vào để xem toàn văn văn bản luật gốc từ hệ thống.
- **🧠 Thông minh & Ghi nhớ**: Tích hợp LangChain Memory cho phép hội thoại nhiều lượt, AI hiểu được các câu hỏi nối tiếp dựa trên ngữ cảnh trước đó.
- **🛡️ Rà soát hợp đồng (Contract Review)**: Phân tích rủi ro pháp lý trong hợp đồng bằng cơ chế đa đại lý (Multi-agents), so sánh trực tiếp với các quy định pháp luật hiện hành.
- **📡 Real-time Streaming**: Trải nghiệm mượt mà với cơ chế Streaming (SSE), phản hồi từng chữ như những ứng dụng AI hàng đầu (ChatGPT, Claude).
- **📊 Theo dõi chi tiết (Observability)**: Tích hợp **LangSmith** để giám sát mọi luồng suy nghĩ và kết quả tìm kiếm của AI.

---

## 🏗️ Kiến trúc hệ thống

```text
┌───────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                  │
│       (Streaming SSE, Markdown Rendering, Zustand)        │
└─────────────┬───────────────────────────────┬─────────────┘
              │                               │
┌─────────────▼───────────────────────────────▼─────────────┐
│                      FastAPI Backend                      │
│      (LangChain, PostgreSQL History, Hybrid Search)       │
└─────────────┬───────────────────────────────┬─────────────┘
              │                               │
┌─────────────▼──────────┐        ┌───────────▼─────────────┐
│  Vector DB (Qdrant)    │        │   Relational (Postgres) │
│  (Vietnam Embeddings)  │        │   (Full text & History) │
└────────────────────────┘        └─────────────────────────┘
```

---

## 🚀 Hướng dẫn khởi động (Setup Guide)

Hệ thống yêu cầu các thành phần nền tảng: **Qdrant** (Vector DB) và **Postgres** (History/Docs). Bạn có thể chạy theo 2 cách:

### Cách 1: Chạy bằng Docker (Khuyên dùng)
Nếu bạn đã cài đặt Docker và Docker Compose, chỉ cần 1 lệnh duy nhất để khởi động toàn bộ:

```bash
docker-compose up -d
```
*Sau đó truy cập:*
- UI: `http://localhost:8080`
- Backend Swagger Docs: `http://localhost:8000/docs`

---

### Cách 2: Chạy Thủ công (Dành cho nhà phát triển)

**1. Khởi động các Database (Infrastructure):**
```bash
docker compose up -d qdrant postgres
```

**2. Cài đặt và chạy Backend:**
```bash
# Tạo môi trường ảo
python3 -m venv venv
source venv/bin/activate

# Cài đặt thư viện
pip install -r requirements.txt

# Khởi động Backend
python -m src.main
```

**3. Cài đặt và chạy Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## 📂 Hướng dẫn nạp dữ liệu (Ingestion)

AI cần được nạp dữ liệu luật để có thể trả lời. Vui lòng tham khảo tài liệu chi tiết tại:
👉 **[Hướng dẫn Nạp dữ liệu (docs/ingestion.md)](docs/ingestion.md)**

**Lệnh nạp nhanh (Test):**
```bash
curl -X POST "http://localhost:8000/ingest/test"
```

---

## 🛠️ Cấu hình hệ thống (.env)

Đảm bảo bạn đã cấu hình các biến môi trường trong file `.env`:
- `GROQ_API_KEY` hoặc `OPENAI_API_KEY`: Để sử dụng mô hình LLM.
- `LANGCHAIN_API_KEY`: (Tùy chọn) Để bật tính năng Tracing với LangSmith.
- `POSTGRES_URL`: Đường dẫn kết nối Postgres.

---

## 📜 Tài liệu bổ trợ
- [Kiến trúc hệ thống chi tiết](docs/ARCHITECTURE.md)
- [Chiến thuật RAG (Retrieval)](docs/LEGAL_RAG_STRATEGY.md)
- [Quy trình Rà soát Hợp đồng](docs/CONTRACT_REVIEW_PIPELINE.md)

---
*Phát triển bởi đội ngũ VinUni Legal AI.*
