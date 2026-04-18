import os
import sys
from huggingface_hub import hf_hub_download

# Thư mục chứa dữ liệu
DATA_DIR = "data/raw"
REPO_ID = "th1nhng0/vietnamese-legal-documents"

FILES_TO_DOWNLOAD = [
    "data/content.parquet",
    "data/metadata.parquet"
]

def download_dataset():
    """Tải toàn bộ dataset từ HuggingFace về local với thanh tiến trình."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"📁 Đã tạo thư mục: {DATA_DIR}")

    print(f"🚀 Bắt đầu tải dữ liệu từ repo: {REPO_ID}")
    
    for file_path in FILES_TO_DOWNLOAD:
        file_name = os.path.basename(file_path)
        print(f"⏳ Đang tải {file_name}...")
        
        try:
            local_path = hf_hub_download(
                repo_id=REPO_ID,
                repo_type="dataset",
                filename=file_path,
                local_dir=DATA_DIR,
                local_dir_use_symlinks=False
            )
            print(f"✅ Đã lưu tại: {local_path}")
        except Exception as e:
            print(f"❌ Lỗi khi tải {file_name}: {e}")

if __name__ == "__main__":
    download_dataset()
    print("\n✨ Hoàn thành quá trình tải dữ liệu!")
