import sys
import os
sys.path.append(os.getcwd())

import json
import pandas as pd
import time
from scripts.crawl_thuvienphapluat import ThuVienPhapLuatCrawler

def backfill_content(limit=None):
    TARGETS_FILE = "data/raw/backfill_targets.json"
    CONTENT_FILE = "data/raw/content.parquet"
    
    if not os.path.exists(TARGETS_FILE):
        print(f"❌ Targets file {TARGETS_FILE} not found. Run find_missing_content.py first.")
        return

    print(f"📖 Loading targets from {TARGETS_FILE}...")
    with open(TARGETS_FILE, "r", encoding="utf-8") as f:
        targets = json.load(f)

    if not targets:
        print("✅ No targets to backfill.")
        return

    if limit:
        targets = targets[:limit]
        print(f"⚠️ Limiting backfill to first {limit} documents for safety.")

    print(f"📖 Loading original content from {CONTENT_FILE}...")
    content_df = pd.read_parquet(CONTENT_FILE)
    content_df["id"] = content_df["id"].astype(str)

    crawler = ThuVienPhapLuatCrawler()
    updated_count = 0
    failed_count = 0

    for i, target in enumerate(targets):
        doc_id = target["id"]
        so_ky_hieu = target["so_ky_hieu"]
        print(f"\n🔄 [{i+1}/{len(targets)}] Processing: {so_ky_hieu} (ID: {doc_id})")

        try:
            # 1. Search for URL
            urls = crawler.search_documents(so_ky_hieu)
            if not urls:
                print(f"⚠️ Could not find URL for {so_ky_hieu}")
                failed_count += 1
                continue
            
            url = urls[0]
            if not url.startswith("http"):
                from urllib.parse import urljoin
                url = urljoin(crawler.base_url, url)

            # 2. Scrape content only
            new_html = crawler.scrape_content_only(url)
            
            if new_html and len(new_html) > 500:
                # 3. Update DataFrame
                # Use .loc to update specifically for this ID
                content_df.loc[content_df["id"] == doc_id, "content_html"] = new_html
                print(f"✅ Successfully fetched {len(new_html)} chars.")
                updated_count += 1
            else:
                print(f"❌ Fetched content too short or empty for {so_ky_hieu}")
                failed_count += 1

            # Sleep to avoid rate limiting
            time.sleep(2)
            if (i + 1) % 5 == 0:
                print("☕ Resting for 5 seconds...")
                time.sleep(5)

        except Exception as e:
            print(f"🔥 Error processing {so_ky_hieu}: {e}")
            failed_count += 1

    if updated_count > 0:
        print(f"\n💾 Saving {len(content_df)} rows to {CONTENT_FILE}...")
        # Make a backup first
        backup_file = CONTENT_FILE + ".bak"
        os.rename(CONTENT_FILE, backup_file)
        print(f"📦 Backup created at {backup_file}")
        
        content_df.to_parquet(CONTENT_FILE, index=False)
        print(f"🎉 Backfill complete! Updated: {updated_count}, Failed: {failed_count}")
    else:
        print("\n⏹️ No updates were made to the dataset.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill missing legal content.")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents for testing")
    args = parser.parse_args()

    backfill_content(limit=args.limit)
