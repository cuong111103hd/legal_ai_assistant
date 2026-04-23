# 🚀 Hướng dẫn Nạp Dữ liệu (Data Ingestion Guide)

Tài liệu này hướng dẫn chi tiết các phương thức nạp dữ liệu pháp luật vào hệ thống Trợ lý Pháp luật Việt Nam. Hệ thống hỗ trợ 3 chế độ nạp dữ liệu khác nhau tùy vào mục đích sử dụng.

---

## 1. Các phương thức Ingestion

### A. Nạp dữ liệu tiêu chuẩn (Filtered Ingestion)
Đây là phương thức dùng cho môi trường Production. Hệ thống sẽ quét toàn bộ bộ dữ liệu và áp dụng các bộ lọc nghiêm ngặt để đảm bảo chất lượng:
- **Loại văn bản**: Chỉ lấy "Luật" và "Bộ luật".
- **Thời gian**: Chỉ lấy văn bản ban hành từ năm **2015** trở về sau.
- **Tình trạng**: Chỉ lấy văn bản "Còn hiệu lực" hoặc "Hết hiệu lực một phần".
- **Từ khóa**: Ưu tiên các văn bản về An ninh mạng và An toàn thông tin.

**Lệnh thực hiện:**
```bash
# Nạp 100 văn bản thỏa mãn điều kiện
curl -X POST "http://localhost:8000/ingest" \
     -H "Content-Type: application/json" \
     -d '{"limit": 100}'
```

---

### B. Nạp dữ liệu theo số hiệu (Targeted Ingestion)
Dùng khi bạn muốn bổ sung đích danh một hoặc nhiều văn bản cụ thể mà không cần quan tâm đến các bộ lọc hệ thống (Bỏ qua bộ lọc năm, loại văn bản, v.v.).

**Lệnh thực hiện:**
```bash
curl -X POST "http://localhost:8000/ingest/by-numbers" \
     -H "Content-Type: application/json" \
     -d '{
       "document_numbers": ["24/2018/QH14", "100/2015/QH13"]
     }'
```

---

### C. Nạp dữ liệu thử nghiệm (Test Ingestion - Unfiltered)
Dùng cho mục đích Debug hoặc Test tính năng Review hợp đồng/Chat nhanh. Phương thức này sẽ lấy **50 văn bản đầu tiên** trong bộ dữ liệu mà **KHÔNG** áp dụng bất kỳ bộ lọc nào.

**Lệnh thực hiện:**
```bash
curl -X POST "http://localhost:8000/ingest/test"
```

---

## 2. Theo dõi trạng thái Ingestion

Vì quá trình nạp dữ liệu bao gồm nhiều bước (Tải -> Lưu SQL -> Chia nhỏ -> Tạo Vector -> Lưu Qdrant), quá trình này sẽ chạy ngầm (Background Task). Bạn có thể kiểm tra tiến độ bằng lệnh sau:

```bash
curl -X GET "http://localhost:8000/ingest/status"
```

**Kết quả trả về mẫu:**
```json
{
  "state": "running",
  "total_documents": 100,
  "processed_documents": 45,
  "total_chunks": 1250,
  "error_message": null
}
```

---

## 3. Lưu ý quan trọng
- **Tự động Reload**: Sau khi quá trình nạp dữ liệu hoàn tất thành công, Backend sẽ tự động tải lại chỉ mục (BM25 & Retriever). Bạn có thể bắt đầu Chat với dữ liệu mới ngay lập tức mà không cần khởi động lại Server.
- **Dữ liệu cục bộ**: Hệ thống ưu tiên đọc file parquet từ `data/raw/` nếu có sẵn để tăng tốc độ nạp. Nếu không thấy file cục bộ, hệ thống sẽ tự động stream dữ liệu từ HuggingFace.
- **Ghi đè**: Các văn bản trùng ID sẽ được cập nhật (Upsert) vào hệ thống thay vì tạo bản sao mới.
