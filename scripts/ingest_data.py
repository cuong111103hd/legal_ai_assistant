import asyncio
import argparse
import sys
import os

# Thêm thư mục gốc vào path để import được src
sys.path.append(os.getcwd())

from src.ingestion import run_ingestion_pipeline

async def main():
    parser = argparse.ArgumentParser(description="Nạp dữ liệu pháp luật vào hệ thống RAG.")
    parser.add_argument("--prefix", type=str, default="", help="Tiền tố file parquet (ví dụ: addition_)")
    parser.add_argument("--mode", type=str, choices=["full", "addition"], default="full", 
                        help="Chế độ nạp: 'full' (xóa cũ nạp mới), 'addition' (chỉ thêm mới)")
    
    args = parser.parse_args()

    recreate = (args.mode == "full")
    
    print(f"🚀 Bắt đầu nạp dữ liệu...")
    print(f"   - Tiền tố file: '{args.prefix}' (Nạp từ {args.prefix}metadata.parquet)")
    print(f"   - Chế độ: {'Xóa cũ nạp mới (Full)' if recreate else 'Chỉ thêm mới (Addition)'}")
    
    status = await run_ingestion_pipeline(prefix=args.prefix, recreate=recreate)
    
    if status.state.value == "completed":
        print("\n✅ Nạp dữ liệu thành công!")
    else:
        print(f"\n❌ Nạp dữ liệu thất bại: {status.error_message}")

if __name__ == "__main__":
    asyncio.run(main())
