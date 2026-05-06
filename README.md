# ⚖️ Trợ Lý Pháp Luật Việt Nam (Legal AI Assistant)

Chào mừng bạn đến với hệ thống Trợ lý Pháp luật Việt Nam thế hệ mới. Đây là một nền tảng **RAG (Retrieval-Augmented Generation)** cấp độ sản xuất (Production-Grade), được thiết kế chuyên sâu để giải quyết các bài toán tra cứu luật pháp, trả lời câu hỏi tư vấn và rà soát rủi ro hợp đồng dựa trên dữ liệu luật chính thống.

---

## ✨ Tính năng chính (Features)

- **🧠 Query Planner (Tiền xử lý thông minh)**: Tự động dịch các từ viết tắt (VD: "BLHS"), đồng nghĩa, và nhận diện phủ định để hiểu chính xác ý định người dùng trước khi tìm kiếm.
- **🔍 Hybrid Search & RRF**: Kết hợp tìm kiếm Vector (Semantic/Qdrant) và Từ khóa (Lexical/OpenSearch) giúp tìm kiếm chính xác kể cả khi người dùng không dùng thuật ngữ chuyên môn.
- **📌 Multi-field Boosted Search**: OpenSearch ưu tiên khớp trên các trường metadata (`article_id`, `document_number`) với trọng số cao hơn, giúp trả về đúng Điều/Khoản ngay cả khi người dùng hỏi đích danh.
- **🕸️ Graph RAG (Neo4j)**: Mở rộng kết quả tìm kiếm bằng đồ thị quan hệ pháp lý (văn bản sửa đổi, bổ sung, thay thế), đảm bảo không bỏ sót các điều khoản liên quan.
- **📜 Deep-link Citations**: Mọi câu trả lời của AI đều đi kèm trích dẫn Điều/Khoản. Người dùng có thể nhấn vào để xem toàn văn văn bản luật gốc.
- **🧠 Thông minh & Ghi nhớ**: Tích hợp LangChain Memory cho phép hội thoại nhiều lượt, AI hiểu được các câu hỏi nối tiếp dựa trên ngữ cảnh trước đó.
- **🛡️ Rà soát hợp đồng (Contract Review)**: Phân tích rủi ro pháp lý trong hợp đồng bằng cơ chế đa đại lý (Multi-agents), so sánh trực tiếp với các quy định pháp luật hiện hành.
- **📡 Real-time Streaming**: Trải nghiệm mượt mà với cơ chế Streaming (SSE), phản hồi từng chữ như những ứng dụng AI hàng đầu.
- **📊 Theo dõi chi tiết (Observability)**: Tích hợp **LangSmith** để giám sát mọi luồng suy nghĩ và kết quả tìm kiếm của AI.

---

## 🏗️ Kiến trúc hệ thống

```text
┌──────────────────────────────────────────────────────────────┐
│                    React + Vite Frontend                     │
│        (Streaming SSE, Markdown Rendering, Zustand)          │
└──────────────────────┬───────────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────────┐
│                      FastAPI Backend                         │
│  (Query Planner → Hybrid Search → Graph RAG → LLM Stream)   │
└────┬──────────────┬──────────────┬──────────────┬────────────┘
     │              │              │              │
┌────▼────┐   ┌─────▼─────┐  ┌────▼────┐  ┌─────▼──────┐
│ Qdrant  │   │OpenSearch │  │  Neo4j  │  │ PostgreSQL │
│(Vector) │   │(Lexical)  │  │ (Graph) │  │(Docs/Hist) │
└─────────┘   └───────────┘  └─────────┘  └────────────┘
```

### Luồng Hybrid Search

```
Câu hỏi người dùng
       ↓
  Query Planner
  (mở rộng từ đồng nghĩa, viết tắt)
       ↓
 ┌─────┴─────┐
 ▼           ▼
Qdrant    OpenSearch
(Dense)   (Sparse/BM25)
 │  article_id × 3
 │  document_number × 2
 │  law_name × 2
 │  content × 1
 └─────┬─────┘
       ▼
   RRF Fusion
       ↓
 Graph Expansion (Neo4j)
       ↓
  Evidence Pack → LLM
```

---

## 🗄️ Hạ tầng Database

| Database | Vai trò | Port |
|---|---|---|
| **Qdrant** | Vector DB — Dense Semantic Search | `6333` |
| **OpenSearch** | Lexical Search — Tìm kiếm từ khóa, Điều/Khoản | `9200` |
| **Neo4j** | Graph DB — Quan hệ văn bản pháp luật | `7687` / `7474` |
| **PostgreSQL** | Lưu trữ văn bản gốc & lịch sử hội thoại | `5432` |

---

## 🚀 Hướng dẫn khởi động (Setup Guide)

### Yêu cầu
- Docker & Docker Compose V2 (`docker compose version`)
- Python 3.12+

### Cách 1: Chạy bằng Docker (Khuyên dùng)

Khởi động toàn bộ hệ thống (bao gồm OpenSearch) chỉ với 1 lệnh:

```bash
docker compose up -d
```

*Sau đó truy cập:*
- Backend Swagger Docs: `http://localhost:8000/docs`
- Neo4j Browser: `http://localhost:7474`

---

### Cách 2: Chạy Thủ công (Dành cho nhà phát triển)

**1. Khởi động tất cả Database:**

```bash
docker compose up -d qdrant postgres neo4j opensearch adminer
```

> ⚠️ **Lưu ý quan trọng**: Từ phiên bản OpenSearch 2.12+, bạn bắt buộc phải cung cấp mật khẩu admin qua biến môi trường `OPENSEARCH_INITIAL_ADMIN_PASSWORD`. Giá trị này đã được cấu hình sẵn trong `docker-compose.yml`.

**2. Cài đặt và chạy Backend:**

```bash
# Tạo môi trường ảo
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt thư viện (bao gồm opensearch-py)
pip install -r requirements.txt

# Sao chép file cấu hình
cp .env.example .env
# Điền các API Key vào .env

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

Có 2 luồng nạp dữ liệu tùy theo môi trường:

### Luồng A: Nạp trực tiếp (trong máy có GPU)

```bash
curl -X POST "http://localhost:8000/ingest" \
     -H "Content-Type: application/json" \
     -d '{"limit": 100}'
```

Dữ liệu sẽ tự động được nạp vào **Qdrant**, **OpenSearch**, và **PostgreSQL** đồng thời.

### Luồng B: Nạp qua Colab (Khuyên dùng cho máy yếu)

Luồng này phù hợp khi bạn tạo embedding trên Google Colab (GPU miễn phí) rồi nạp về:

**Bước 1:** Xuất dữ liệu thô để đưa lên Colab:
```bash
python scripts/export_for_colab.py
```

**Bước 2:** Chạy notebook trên Colab để tạo embeddings.

**Bước 3:** Tải file `vectors.parquet` về `data/interim/`, sau đó chạy:
```bash
python scripts/import_from_colab.py
```

Script này sẽ đồng thời nạp dữ liệu vào:
- ✅ **Qdrant** (Dense Vectors)
- ✅ **OpenSearch** (Full-text + Metadata)
- ✅ **PostgreSQL** (Quan hệ pháp lý)

**Bước 4:** Xây dựng đồ thị quan hệ trong Neo4j:
```bash
python scripts/build_graph.py
```

---

## 🛠️ Cấu hình hệ thống (.env)

| Biến môi trường | Mô tả | Bắt buộc |
|---|---|---|
| `GROQ_API_KEY` hoặc `OPENAI_API_KEY` | API Key cho LLM | ✅ |
| `OPENSEARCH_HOST` | Host của OpenSearch | ✅ (mặc định: `localhost`) |
| `OPENSEARCH_PORT` | Port của OpenSearch | ✅ (mặc định: `9200`) |
| `OPENSEARCH_INDEX` | Tên index trong OpenSearch | ✅ (mặc định: `vietnamese_legal`) |
| `QDRANT_HOST` | Host của Qdrant | ✅ (mặc định: `localhost`) |
| `NEO4J_URI` | URI kết nối Neo4j | ✅ |
| `POSTGRES_HOST` | Host của PostgreSQL | ✅ |
| `CONTEXT_WINDOW` | Số chunk liền kề được nạp thêm | Không (mặc định: `0`) |
| `LANGCHAIN_API_KEY` | API Key LangSmith (Tracing) | Không |

---

## 📜 Tài liệu bổ trợ

- [Kiến trúc hệ thống chi tiết](docs/ARCHITECTURE.md)
- [Chiến thuật RAG (Retrieval)](docs/LEGAL_RAG_STRATEGY.md)
- [Quy trình Rà soát Hợp đồng](docs/CONTRACT_REVIEW_PIPELINE.md)

---

*Phát triển bởi đội ngũ VinUni Legal AI.*
