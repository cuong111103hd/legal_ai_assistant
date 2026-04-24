# Báo Cáo Giai Đoạn 1: Tích hợp Query Planner (Merge Reference)

Báo cáo này tổng hợp những thay đổi, mức độ tái sử dụng code từ dự án `reference_nam` và cấu trúc hiện tại của dự án chính sau Giai đoạn 1.

## 1. Những Gì Đã Thay Đổi (Changes)
- **Thêm tính năng Query Planning**: Tích hợp một module mới có khả năng bóc tách, dịch các từ viết tắt (như "BLHS", "TT-BTC"), tìm từ đồng nghĩa, và phát hiện câu phủ định từ câu hỏi của người dùng.
- **Nâng cấp Hybrid Retriever**: 
  - Vector Search (Qdrant) tiếp tục sử dụng câu hỏi gốc để giữ nguyên ngữ nghĩa.
  - Sparse Search (BM25) được nâng cấp để tìm kiếm cùng lúc cả câu hỏi gốc và các từ khóa mở rộng (Expansion Variants) sinh ra bởi Planner. Việc này giúp cải thiện độ bao phủ (Recall) cực lớn, tránh tình trạng "gõ không đúng từ thì không ra".
- **Cập nhật Generator Pipeline**: RAG Engine hiện tại sẽ tự động chạy Query Planner trước khi gọi Retriever trong cả chế độ QA thông thường và Streaming.

## 2. Những Gì Được Giữ Lại Từ Dự Án Chính (Kept from Main)
Theo đúng phương án A mà bạn đã chọn:
- **Giữ nguyên Ingestion Pipeline & Beautiful Soup**: Cơ chế cắt chunk theo "Điều" (`chunk_html_by_article`) của dự án chính được giữ lại toàn bộ. Văn bản lưu vào database vẫn giữ nguyên cấu trúc HTML, đảm bảo giao diện frontend hiển thị đẹp mắt (in đậm, in nghiêng, xuống dòng).
- **Giữ nguyên Local BM25 (`.pkl`)**: Không cài đặt thêm OpenSearch ở giai đoạn này. BM25 cục bộ tiếp tục hoạt động nhẹ nhàng nhưng được tăng lực nhờ Planner.
- **Giữ nguyên Vector DB (Qdrant) và LLM Prompting**: Luồng giao tiếp với LLM và truy vấn Qdrant không thay đổi cốt lõi, đảm bảo tính ổn định.

## 3. Những Gì Được Lấy Từ Reference (Taken from Reference)
- **Module LegalQueryPlanner**: Được **sao chép trực tiếp** từ `reference_nam/packages/reasoning/planner.py` sang `src/planner.py`.
- **Từ điển pháp lý (Legal Dictionaries)**: Toàn bộ bộ từ điển viết tắt, từ đồng nghĩa và logic nhận diện luật/khoản/điểm của Reference được tái sử dụng 100%.

### Mức Độ Tận Dụng Reference: ~90% (Dành riêng cho module Planner)
- **Code tận dụng nguyên bản**: `src/planner.py` hầu như giữ nguyên 90% logic của Reference. Chỉ sửa đổi duy nhất đường dẫn `import` (đổi `from packages.common.types` thành `from .models`) để tương thích với cấu trúc của dự án chính. Không có chức năng nào bị loại bỏ.
- **Code viết mới (Glue Code)**: Khoảng 10% công việc là viết "mã keo" để gắn cái Planner này vào `generator.py` và `retriever.py` đang có sẵn của dự án chính.

## Kết Luận
Giai đoạn 1 đã hoàn tất thành công. AI hiện tại đã thông minh hơn ở khâu nhận diện câu hỏi mà không làm phá vỡ sự ổn định của hệ thống hiện tại. Dữ liệu HTML của bạn hoàn toàn không bị ảnh hưởng.
