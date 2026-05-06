# Hướng dẫn chạy Embedding trên Google Colab

Dưới đây là đoạn code Python chuẩn bị sẵn để bạn chạy trên Google Colab sau khi đã xuất file `to_embed.parquet` từ máy tính.

### Các bước thực hiện:

1. Vào [Google Colab](https://colab.research.google.com/) tạo sổ tay mới.
2. Vào mục **Runtime > Change runtime type** và chọn **T4 GPU** (hoặc L4).
3. Upload file `data/interim/to_embed.parquet` vào phần Files bên trái của Colab.
4. Cài đặt thư viện cần thiết bằng lệnh sau trong 1 cell:

```bash
!pip install -q pandas pyarrow sentence-transformers
```

5. Chạy đoạn code Python sau trong 1 cell mới:

```python
import pandas as pd
from sentence_transformers import SentenceTransformer

print("1. Đang tải dữ liệu...")
df = pd.read_parquet("to_embed.parquet")
print(f"Tổng số chunks cần nhúng: {len(df)}")

print("\n2. Đang tải mô hình (có thể mất vài phút)...")
# Đổi mô hình tại đây nếu bạn dùng model khác trong settings.EMBEDDING_MODEL
model = SentenceTransformer("keepitreal/vietnamese-sbert") 

print("\n3. Đang thực hiện Embedding trên GPU...")
# Bước này sẽ chạy siêu nhanh trên GPU
embeddings = model.encode(df["content"].tolist(), show_progress_bar=True)

print("\n4. Đang lưu kết quả...")
df_vectors = pd.DataFrame({
    "chunk_id": df["chunk_id"],
    "vector": list(embeddings)
})

df_vectors.to_parquet("vectors.parquet", index=False)
print("Hoàn tất! Hãy tải file 'vectors.parquet' về máy tính của bạn.")
```

6. Sau khi chạy xong, tải file `vectors.parquet` (mới xuất hiện ở cột Files bên trái) về máy tính và lưu vào thư mục `data/interim/`.
7. Chạy script `scripts/import_from_colab.py` ở máy của bạn để hoàn tất Ingestion.

```bash
# python scripts/import_from_colab.py 
1. Đang khởi tạo Database SQL...
2. Đang nạp Documents vào PostgreSQL...
  ✓ Đã nạp 268 văn bản.
3. Đang trích xuất quan hệ pháp lý từ văn bản...
  ✓ Tìm thấy 58 quan hệ.
4. Đang xử lý Vector từ Colab...
5. Đang Upsert 69457 chunks vào Qdrant...
  ✓ Đã nạp xong Vectors!
6. Resolving Target Documents trong SQL...
  ✓ Đã resolve thành công 38 quan hệ.
```