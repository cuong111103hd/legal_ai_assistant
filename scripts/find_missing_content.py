import pandas as pd
import os
import json

def find_missing_content():
    LOCAL_META = "data/raw/metadata.parquet"
    LOCAL_CONTENT = "data/raw/content.parquet"
    OUTPUT_FILE = "data/raw/backfill_targets.json"

    if not os.path.exists(LOCAL_META) or not os.path.exists(LOCAL_CONTENT):
        print(f"❌ Parquet files not found in data/raw/")
        return

    print("📖 Loading datasets...")
    meta_df = pd.read_parquet(LOCAL_META)
    content_df = pd.read_parquet(LOCAL_CONTENT)
    
    meta_df["id"] = meta_df["id"].astype(str)
    content_df["id"] = content_df["id"].astype(str)
    
    # Merge
    df = pd.merge(content_df, meta_df, on="id", how="left")
    
    print(f"📊 Total documents in dataset: {len(df)}")

    # Apply filters from src/ingestion.py
    # 1. Type filter
    if 'loai_van_ban' in df.columns:
        target_types = ['Luật', 'Bộ luật']
        df = df[df['loai_van_ban'].astype(str).isin(target_types)]
    
    # 2. Status filter
    if 'tinh_trang_hieu_luc' in df.columns:
        target_status = ['Còn hiệu lực', 'Hết hiệu lực một phần']
        df = df[df['tinh_trang_hieu_luc'].astype(str).isin(target_status)]
    
    # 3. Year filter
    if 'ngay_ban_hanh' in df.columns:
        # Convert to datetime, format is DD/MM/YYYY
        df['dt_ban_hanh'] = pd.to_datetime(df['ngay_ban_hanh'], format='%d/%m/%Y', errors='coerce')
        df = df[df['dt_ban_hanh'].dt.year >= 2000]

    print(f"📊 Documents matching ingestion standards: {len(df)}")

    # 4. Content length filter (THE CORE OF THIS TASK)
    if 'content_html' in df.columns:
        # We want the ones that FAIL the > 500 test
        missing_mask = df['content_html'].astype(str).str.len() <= 500
        targets_df = df[missing_mask]
    else:
        targets_df = df # All are missing if column doesn't exist

    print(f"🎯 Documents with missing/short content (<= 500 chars): {len(targets_df)}")

    if len(targets_df) == 0:
        print("✅ No missing content found. Everything looks good!")
        return

    # Extract target info
    targets = []
    for _, row in targets_df.iterrows():
        targets.append({
            "id": str(row.get("id")),
            "so_ky_hieu": str(row.get("so_ky_hieu")),
            "title": str(row.get("title")),
            "current_len": len(str(row.get("content_html")))
        })

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(targets, f, ensure_ascii=False, indent=2)

    print(f"✅ Saved {len(targets)} targets to {OUTPUT_FILE}")

if __name__ == "__main__":
    find_missing_content()
