# Vietnamese Legal Assistant 🇻🇳⚖️

Trợ lý pháp luật Việt Nam (Thế hệ 2) sử dụng kiến trúc **RAG (Retrieval-Augmented Generation)** tiên tiến, kết hợp giữa tìm kiếm Vector (Semantic) và Từ khóa (Lexical) với khả năng ghi nhớ hội thoại thông minh. Hệ thống chuyên sâu về luật Việt Nam, cung cấp trích dẫn chính xác và cho phép tra cứu toàn văn văn bản luật ngay lập tức.

## 🏗 Kiến trúc hệ thống (Generation 2)

```text
┌────────────────────────────────────────────────────────────────────────────┐
│                             FastAPI Server                                 │
│  /chat (Memory) │ /review-contract │ /sessions (History) │ /documents (Full)│
├────────────────────────────────────────────────────────────────────────────┤
│                    Generation & Logic Engine (LangChain)                   │
│          Groq/OpenAI + Conversation Memory + EvidencePack Prompting        │
├─────────────┬──────────────────────────────────────┬───────────────────────┤
│   Retriever │ Search Dense (Qdrant) + Sparse (BM25)│ RRF Fusion + Context  │
├─────────────┴──────────────────────────────────────┴───────────────────────┤
│                               Data Layer                                   │
│  Vector DB (Qdrant) │ Relational DB (PostgreSQL) │ BM25 Index & Metadata   │
├────────────────────────────────────────────────────────────────────────────┤
│                            Ingestion Pipeline                              │
│  Parquet Data → In-depth Chunking → SQL (Full Text) → Qdrant (Embeddings)  │
└────────────────────────────────────────────────────────────────────────────┘
```

## ✨ Tính năng nổi bật

- **Hybrid Search & RRF**: Kết hợp sức mạnh của Qdrant (hiểu ý nghĩa) và BM25 (tìm chính xác từ khóa) với thuật toán Reciprocal Rank Fusion.
- **Persistent Chat History**: Sử dụng **PostgreSQL** và **LangChain** để lưu trữ và ghi nhớ lịch sử hội thoại trên nhiều phiên. AI có khả năng hiểu ngữ cảnh từ các câu hỏi trước đó.
- **Deep-Link Citations**: Mọi trích dẫn pháp luật trong câu trả lời đều có mã định danh. Người dùng có thể nhấn vào trích dẫn để xem **toàn văn văn bản luật** được lưu trữ trong SQL.
- **Parallel Clause Review**: Tính năng rà soát hợp đồng sử dụng cơ chế song song (Parallel Sub-Agents) để phân tích từng điều khoản, nhận diện rủi ro dựa trên cơ sở luật thực tế.
- **No-Hallucination Policy**: Cam kết không ảo giác. Mọi câu trả lời bắt buộc phải dựa trên dữ liệu luật hiện hành được tìm thấy.
- **Real-time Streaming**: Trả lời từng chữ (streaming) qua Server-Sent Events (SSE) mang lại cảm giác phản hồi tức thì.

## 📁 Cấu trúc dự án

```text
legal_AI_assistant/
├── src/                    # 🧠 Logic Backend (FastAPI + Python)
│   ├── database.py         # Quản lý Qdrant (Vector storage)
│   ├── database_sql.py     # Quản lý PostgreSQL (History & Full text)
│   ├── ingestion.py        # Pipeline nạp dữ liệu vào cả 2 DB
│   ├── retriever.py        # Bộ máy tìm kiếm lai tích hợp Deep-link
│   ├── generator.py        # LangChain Agent + Conversation Memory
│   ├── main.py             # API Endpoints (v2)
│   └── models.py           # Pydantic v2 schemas
├── frontend/               # 🎨 Giao diện Người dùng (React + Vite + Zustand)
├── docker-compose.yml      # Chạy đồng bộ Qdrant & PostgreSQL
└── requirements.txt        # Danh sách thư viện Python (LangChain, SQLAlchemy, ...)
```

## 🚀 Hướng dẫn khởi động

Dự án có thể chạy hoàn toàn bằng Docker hoặc chạy từng phần bằng tay (khuyên dùng khi phát triển).

### Cách 1: Chạy toàn bộ Backend bằng Docker (Nhanh nhất)
Lệnh này sẽ khởi động **Qdrant**, **PostgreSQL** và cả **FastAPI Backend (API)**.
```bash
docker compose up -d
```
> **Lưu ý**: Sau khi chạy lệnh này, API Backend sẽ nằm tại: `http://localhost:8000`

### Cách 2: Chạy Backend bằng Python (Để phát triển)
Nếu bạn muốn sửa code Backend và thấy thay đổi ngay lập tức:
1. **Chạy 2 cơ sở dữ liệu (Bắt buộc)**:
   ```bash
   docker compose up -d qdrant postgres
   ```
2. **Chạy API Backend**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python -m src.main
   ```

### 3. Khởi động Giao diện Web (Frontend) 🔥
Frontend là một dự án React riêng biệt chạy trên Vite. **Bạn phải chạy lệnh này để có giao diện sử dụng.**

```bash
cd frontend
npm install
npm run dev
```

> **Giao diện người dùng (UI)**: [http://localhost:8080/](http://localhost:8080/)
> **Tài liệu API (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🏗️ Luồng sử dụng (Dành cho lần đầu)

1. **Khởi động Backend & DBs** (Xem bước trên).
2. **Nạp dữ liệu**: AI cần có luật trong bụng mới trả lời được. Hãy gọi lệnh nạp 100 văn bản mẫu:
   ```bash
   curl -X POST "http://localhost:8000/ingest" -H "Content-Type: application/json" -d '{"limit": 100}'
   ```
3. **Kiểm tra tiến độ**: Bạn có thể theo dõi xem đã nạp được bao nhiêu % bằng lệnh:
   ```bash
   curl -X GET "http://localhost:8000/ingest/status"
   ```
4. **Mở giao diện**: Truy cập [http://localhost:8080](http://localhost:8080) và bắt đầu chat!


---

## 📡 API Endpoints (v2)

| Nhóm | Method | Endpoint | Mô tả |
|------|--------|----------|-------|
| **Chat** | `POST` | `/chat` | Chat với bộ nhớ (LangChain Memory) |
| **Sessions** | `GET` | `/sessions` | Danh sách các phiên hội thoại cũ |
| **History** | `GET` | `/sessions/{id}/messages` | Lấy tin nhắn trong một session |
| **Docs** | `GET` | `/documents/{id}` | Lấy toàn văn văn bản luật (Deep-link) |
| **Review** | `POST` | `/review-contract` | Rà soát rủi ro hợp đồng |
| **Admin** | `POST` | `/ingest` | Nạp dữ liệu đồng bộ Qdrant + SQL |

---

## ⚙️ Cấu hình quan trọng (.env)

| Biến | Ý nghĩa |
|------|---------|
| `POSTGRES_URL` | Liên kết kết nối database SQL (History & Fulltext) |
| `QDRANT_HOST` | Địa chỉ server Qdrant Vector |
| `EMBEDDING_MODEL` | Mô hình nhúng tiếng Việt (Quockhanh05/...) |
| `LLM_PROVIDER` | `openai` hoặc `groq` |

---

## 🛡️ Ghi nhật ký & Phát triển
Dự án được tích hợp cơ chế ghi log tự động cho các AI Agent. Vui lòng tham khảo [AGENTS.md](./AGENTS.md) để biết thêm chi tiết về quy tắc đóng góp.
