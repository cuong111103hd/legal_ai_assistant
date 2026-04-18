# Chiến Thuật Chunking & Retrieval cho Văn Bản Luật

Tài liệu này chi tiết hóa cách hệ thống xử lý, lưu trữ và tìm kiếm dữ liệu pháp luật Việt Nam để đảm bảo độ chính xác tối đa trong mô hình RAG.

## 1. Chiến Thuật Chunking (Phân mảnh dữ liệu)

Văn bản luật Việt Nam có cấu trúc phân cấp chặt chẽ: **Chương > Mục > Điều > Khoản > Điểm**. Việc chunking tùy tiện theo độ dài (Fixed-size chunking) sẽ làm mất ngữ cảnh.

### Chiến thuật áp dụng: **Semantic Hierarchy Splitter**

- **Đơn vị cơ sở**: Mỗi đoạn (chunk) được tách dựa trên đơn vị **Điều**.
- **Xử lý Điều dài**: Nếu một Điều quá dài (nhiều Khoản phức tạp), hệ thống sẽ tách tiếp theo từng **Khoản**, nhưng luôn đính kèm tiêu đề của Điều đó vào nội dung chunk để giữ ngữ cảnh.
- **Metadata đi kèm**:
    - `law_name`: Tên văn bản (ví dụ: Bộ luật Dân sự 2015).
    - `article_id`: Số hiệu Điều (ví dụ: Điều 168).
    - `validity_status`: Tình trạng hiệu lực.
    - `doc_type`: Loại văn bản (Luật, Nghị định, Thông tư).

---

## 2. Chiến Thuật Retrieval (Tìm kiếm tích hợp)

Hệ thống sử dụng mô hình **Hybrid Search** kết hợp giữa tìm kiếm ngữ nghĩa và tìm kiếm từ khóa chính xác.

### A. Dense Retrieval (Tìm kiếm Vector)
- **Model**: Sử dụng các mô hình Embedding tối ưu cho tiếng Việt (như `paraphrase-multilingual-MiniLM-L12-v2` hoặc các model chuyên sâu về luật).
- **Mục tiêu**: Tìm các đoạn văn có ý nghĩa tương đương với câu hỏi ngay cả khi không trùng từ khóa (ví dụ: hỏi về "nghỉ việc" có thể tìm thấy "chấm dứt hợp đồng lao động").

### B. Sparse Retrieval (BM25)
- **Cơ chế**: Dựa trên tần suất xuất hiện của các thuật ngữ chuyên môn.
- **Mục tiêu**: Bắt chính xác các định danh pháp lý hoặc từ khóa đặc thù (ví dụ: "Điều 168", "Thông tư 45/2019/QH14").

### C. Cơ chế Rank Fusion (RRF)
Sử dụng **Reciprocal Rank Fusion (RRF)** để gộp kết quả từ hai phương thức trên:
$$Score(d) = \sum_{r \in R} \frac{1}{k + r(d)}$$
Giúp cân bằng giữa việc hiểu ý nghĩa và việc tìm đúng thuật ngữ.

---

## 3. Contextual Enrichment (Làm giàu ngữ cảnh)

Sau khi tìm được các chunk liên quan nhất, hệ thống thực hiện **Context Injection**:
1. Lấy thêm các Điều/Khoản lân cận (trước và sau) của chunk tìm được.
2. Gộp lại thành một **Evidence Pack**.
3. Việc này giúp LLM hiểu được các quy định loại trừ hoặc bổ sung thường nằm ở các Điều kế tiếp trong văn bản luật.

---

## 4. Kiểm soát chất lượng (Guardrails)
- **Deduplication**: Loại bỏ các đoạn trùng lặp nếu kết quả trả về từ nhiều văn bản giống nhau.
- **Validity Check**: Ưu tiên các văn bản "Còn hiệu lực" thông qua bộ lọc metadata ở cấp độ database (Qdrant filter).
