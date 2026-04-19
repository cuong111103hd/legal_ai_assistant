# Hướng dẫn Quản trị Cơ sở dữ liệu

Tài liệu này cung cấp thông tin chi tiết về các hệ quản trị cơ sở dữ liệu được sử dụng trong dự án và cách truy cập chúng qua giao diện Web.

## 1. Giao diện Quản trị PostgreSQL (Adminer)

Chúng tôi đã tích hợp **Adminer**, một công cụ quản lý cơ sở dữ liệu trực quan qua trình duyệt.

- **Địa chỉ truy cập**: [http://localhost:8081](http://localhost:8081)
- **Lệnh khởi động**: `docker-compose up -d adminer`

### Thông tin đăng nhập mặc định:
- **Hệ quản trị (System)**: `PostgreSQL`
- **Máy chủ (Server)**: `postgres`
- **Người dùng (Username)**: `legal_user`
- **Mật khẩu (Password)**: `legal_pass`
- **Cơ sở dữ liệu (Database)**: `legal_assistant`

---

## 2. Giao diện Vector Database (Qdrant Dashboard)

Qdrant cung cấp sẵn một bảng điều khiển để kiểm tra các vector (embeddings) và metadata của từng chunk văn bản.

- **Địa chỉ truy cập**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- **Lệnh khởi động**: `docker-compose up -d qdrant`

---

## 3. Cách thay đổi thông tin tài khoản

Nếu bạn muốn thay đổi mật khẩu hoặc tên người dùng, bạn cần cập nhật đồng bộ ở **CẢ 2 NƠI** sau:

1. **File `.env`**: Cập nhật biến `POSTGRES_URL`.
   * Cấu trúc: `postgresql+asyncpg://<Username>:<Password>@localhost:<Port>/<Database>`
2. **File `docker-compose.yml`**: Cập nhật mục `environment` của service `postgres`.

**Lưu ý**: Sau khi thay đổi, bạn phải chạy lại lệnh sau để áp dụng cấu hình mới:
```bash
docker-compose up -d --force-recreate postgres
```

---

## 4. Các bảng dữ liệu chính trong PostgreSQL

- `legal_documents`: Lưu trữ toàn văn các văn bản pháp luật, số hiệu, loại văn bản và trạng thái hiệu lực.
- `chat_sessions`: Quản lý danh sách các phiên hội thoại của người dùng.
- `chat_messages`: Lưu trữ lịch sử tin nhắn và các trích dẫn (citations) đi kèm.
