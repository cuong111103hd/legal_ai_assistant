import pandas as pd

# Xem metadata
meta = pd.read_parquet('data/raw/data/metadata.parquet')
print("--- CẤU TRÚC METADATA ---")
print(meta.columns.tolist())

# Xem nội dung luật
content = pd.read_parquet('data/raw/data/content.parquet')
print("\n--- CẤU TRÚC CONTENT ---")
print(content.columns.tolist())
print("\nVí dụ nội dung luật đầu tiên:")
print(content['content_html'].iloc[0][:20000]) # Xem 500 ký tự đầu
