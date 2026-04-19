# Hướng dẫn sử dụng Docker cho Qdrant (Legal AI)

Tài liệu này hướng dẫn các thao tác cơ bản để quản lý container Qdrant phục vụ cho dự án Legal AI Assistant.

## 1. Chạy lần đầu tiên (Khởi tạo)
Sử dụng lệnh này khi bạn chưa bao giờ tạo container `legal_qdrant`. Lệnh này sẽ tải image, tạo container và mount dữ liệu vào thư mục cục bộ.

```bash
docker run -d -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/qdrant_storage:/qdrant/storage \
    --name legal_qdrant \
    qdrant/qdrant:latest
```

## 2. Kiểm tra tình trạng Container
Để biết container đang chạy hay đã dừng, và sử dụng các cổng nào:

* **Xem các container đang chạy:**
  ```bash
  docker ps
  ```
* **Xem tất cả container (kể cả đã dừng):**
  ```bash
  docker ps -a
  ```

## 3. Khởi động lại (Start)
Sử dụng lệnh này khi bạn đã tắt máy hoặc đã dùng lệnh `stop` trước đó. Dữ liệu sẽ tiếp tục được lưu vào thư mục `qdrant_storage`.

```bash
docker start legal_qdrant
```

## 4. Dừng container (Stop)
Khi bạn muốn tạm nghỉ hoặc bảo trì hệ thống:

```bash
docker stop legal_qdrant
```

## 5. Xem Log (Nhật ký hoạt động)
Dùng để kiểm tra xem Qdrant có hoạt động ổn định không hoặc khi gặp lỗi:

* **Xem log hiện tại:**
  ```bash
  docker logs legal_qdrant
  ```
* **Xem log thời gian thực (Follow):**
  ```bash
  docker logs -f legal_qdrant
  ```

## 6. Xóa và làm lại từ đầu (Nếu cần)
Nếu bạn muốn xóa container để thay đổi cấu hình khởi chạy (thường không làm mất dữ liệu trong thư mục `qdrant_storage` vì đã mount ra ngoài):

```bash
docker rm -f legal_qdrant
```

---
*Lưu ý: Luôn đảm bảo bạn đang ở thư mục gốc của dự án khi chạy các lệnh có sử dụng `$(pwd)`.*
