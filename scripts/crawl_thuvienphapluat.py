#pip install requests beautifulsoup4 pandas pyarrow
import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
import os
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ThuVienPhapLuatCrawler:
    def __init__(self):
        self.base_url = "https://thuvienphapluat.vn"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        })
        self.data_dir = "data/raw"
        os.makedirs(self.data_dir, exist_ok=True)

    def double_url_encode(self, text: str) -> str:
        return quote(quote(text, safe=""), safe="")

    def get_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return BeautifulSoup(response.content, 'html.parser')
            except Exception as e:
                logger.warning(f"Error fetching {url} (attempt {attempt + 1}): {e}")
                time.sleep(2 ** attempt)
        return None

    def search_documents(self, keyword: str) -> List[str]:
        """Search for documents and return a list of primary detail URLs."""
        # Use quotes for exact search if it looks like a document number
        search_keyword = self.double_url_encode(keyword)
        search_url = f"https://thuvienphapluat.vn/page/tim-van-ban.aspx?keyword={search_keyword}&area=2&type=0&status=0&lan=1&org=0&signer=0&match=False&sort=1"
        logger.info(f"Searching for: {keyword}")
        soup = self.get_page(search_url)
        if not soup:
            return []

        links = []
        # Target primary title links: exclude auxiliary links with 'tab='
        # Structural selector: .content-list p.noidung a:first-of-type
        found_elements = soup.select('a[href*="/van-ban/"]:not([href*="tab="])')
        logger.info(f"Found {len(found_elements)} elements.")
    
        for a in found_elements:
            href = a.get('href', '')
            # Filter: only accept links that are Laws or Codes
            if "/Luat" in href or "/Bo-luat" or "/Bo-Luat" in href:
                links.append(href)

        links = links[:1]
        return links

    def extract_ajax_params(self, html: str) -> Dict[str, str]:
        """Extract LawID and checksum from the page source."""
        params = {"law_id": "", "checksum": ""}
        # Try finding in common JS patterns or hidden inputs
        law_id_match = re.search(r"lawid\s*=\s*['\"](\d+)['\"]", html, re.I)
        if not law_id_match:
            law_id_match = re.search(r"LawID=(\d+)", html)
        
        checksum_match = re.search(r"checksum=([^\"'& ]+)", html)
        
        if law_id_match: params["law_id"] = law_id_match.group(1)
        if checksum_match: params["checksum"] = checksum_match.group(1).replace("&amp;", "&")
        
        return params

    def fetch_extra_data(self, law_id: str, checksum: str, endpoint: str) -> str:
        """Fetch extra data from an AJAX endpoint."""
        if not law_id or not checksum:
            return ""
        
        url = f"{self.base_url}/AjaxLoadData/{endpoint}.aspx?LawID={law_id}&checksum={checksum}"
        logger.info(f"Fetching extra data from: {endpoint}")
        try:
            response = self.session.get(url, timeout=20)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.warning(f"Error fetching extra data {endpoint}: {e}")
        return ""

    def scrape_document_detail(self, url: str, keyword: str) -> Optional[Dict]:
        """
        Scrape details of a specific legal document.
        Includes extra data like 'Lược đồ' and 'Dự thảo' via AJAX.
        """
        logger.info(f"Scraping document: {url}")
        soup = self.get_page(url)
        if not soup:
            return None

        html_source = str(soup)

        try:
            # Extract ID from URL
            doc_id_match = re.search(r'/van-ban/.*?/(\d+)\.aspx', url)
            doc_id = doc_id_match.group(1) if doc_id_match else str(int(time.time()))

            title = soup.select_one("h1").get_text(strip=True) if soup.select_one("h1") else "Unknown Title"
            
            content_div = soup.select_one("#divNoiDung") or soup.select_one(".content1")
            content_html = str(content_div) if content_div else ""

            # Extract AJAX params for Lược đồ/Dự thảo
            ajax_params = self.extract_ajax_params(html_source)
            law_id = ajax_params["law_id"]
            checksum = ajax_params["checksum"]

            # Fetch extra sections
            luoc_do_html = self.fetch_extra_data(law_id, checksum, "LoadLuocDo")
            du_thao_html = self.fetch_extra_data(law_id, checksum, "LoadDuThaos")
            lien_quan_html = self.fetch_extra_data(law_id, checksum, "LoadLQHL")

            logger.info(f"Extra data lengths - LuocDo: {len(luoc_do_html)}, DuThao: {len(du_thao_html)}, LQHL: {len(lien_quan_html)}")
            
            # Save LuocDo to a markdown file for debugging if content exists
            # if luoc_do_html and len(luoc_do_html) > 100:
            #     md_path = os.path.join(self.data_dir, f"debug_luoc_do_{doc_id}.md")
            #     with open(md_path, "w", encoding="utf-8") as f:
            #         f.write(f"# Lược đồ văn bản: {title}\n\n")
            #         f.write(f"URL: {url}\n\n")
            #         f.write("## Nội dung Lược đồ (HTML)\n\n")
            #         f.write(luoc_do_html)
            #     logger.info(f"Saved LuocDo content to {md_path}")

            # Removed appending extra info to content to keep content_html clean

            # Initialize metadata
            metadata = {
                "id": doc_id,
                "title": title,
                "so_ky_hieu": keyword,
                "ngay_ban_hanh": "Đang cập nhật",
                "loai_van_ban": "Đang cập nhật",
                "ngay_co_hieu_luc": "Đang cập nhật",
                "ngay_het_hieu_luc": "Đang cập nhật",
                "nguon_thu_thap": "thuvienphapluat.vn",
                "ngay_dang_cong_bao": "Đang cập nhật",
                "nganh": "Đang cập nhật",
                "linh_vuc": "Đang cập nhật",
                "co_quan_ban_hanh": "Đang cập nhật",
                "chuc_danh": "Đang cập nhật",
                "nguoi_ky": "Đang cập nhật",
                "pham_vi": "Toàn quốc",
                "thong_tin_ap_dung": "Đang cập nhật",
                "tinh_trang_hieu_luc": "Còn hiệu lực",
                "url": url,
                "content_html": content_html,
            }

            # --- Extract metadata from the main page first ---
            def parse_meta_table(table_soup, current_meta, mapping):
                if not table_soup: return
                rows = table_soup.find_all("tr")
                seen_fields = set()
                for row in rows:
                    cells = row.find_all("td")
                    for i in range(len(cells)):
                        raw_text = cells[i].get_text(strip=True).lower().replace(":", "")
                        if not raw_text: continue
                        for k, field in mapping.items():
                            if k == raw_text and field not in seen_fields:
                                if i + 1 < len(cells):
                                    val = cells[i+1].get_text(strip=True)
                                    if val and len(val) > 1:
                                        current_meta[field] = val
                                        seen_fields.add(field)
                                        # logger.info(f"  -> {field}: {val}")
                                break

            # Map Thuvienphapluat table keys to our metadata fields
            key_mapping = {
                "loại văn bản": "loai_van_ban",
                "ngày ban hành": "ngay_ban_hanh",
                "ngày có hiệu lực": "ngay_co_hieu_luc",
                "ngày hiệu lực": "ngay_co_hieu_luc",
                "ngày hết hiệu lực": "ngay_het_hieu_luc",
                "ngày đăng công báo": "ngay_dang_cong_bao",
                "cơ quan ban hành": "co_quan_ban_hanh",
                "người ký": "nguoi_ky",
                "chức danh": "chuc_danh",
                "phạm vi": "pham_vi",
                "lĩnh vực": "linh_vuc",
                "ngành": "nganh",
                "tình trạng hiệu lực": "tinh_trang_hieu_luc",
                "thông tin áp dụng": "thong_tin_ap_dung"
            }

            for table in soup.find_all("table"):
                table_text = table.get_text().lower()
                if any(k in table_text for k in ["ngày ban hành", "cơ quan ban hành", "người ký"]):
                    logger.info("Metadata table found on main page. Parsing fields...")
                    parse_meta_table(table, metadata, key_mapping)
                    break

            # --- Supplement metadata from LuocDo HTML ---
            if luoc_do_html:
                logger.info("Supplementing metadata from LuocDo content...")
                luoc_do_soup = BeautifulSoup(luoc_do_html, 'html.parser')
                
                luoc_do_mapping = {
                    "số hiệu": "so_ky_hieu",
                    "loại văn bản": "loai_van_ban",
                    "lĩnh vực, ngành": "linh_vuc",
                    "nơi ban hành": "co_quan_ban_hanh",
                    "người ký": "nguoi_ky",
                    "ngày đăng": "ngay_dang_cong_bao",
                    "ngày hiệu lực": "ngay_co_hieu_luc",
                    "ngày ban hành": "ngay_ban_hanh"
                }
                
                # The LuocDo on Thuvienphapluat uses div.att with div.hd (key) and div.ds (value)
                att_divs = luoc_do_soup.select("div.att")
                if not att_divs:
                    # Fallback to searching all divs if class names differ
                    att_divs = luoc_do_soup.find_all("div")

                for div in att_divs:
                    hd = div.select_one(".hd")
                    ds = div.select_one(".ds")
                    if hd and ds:
                        raw_key = hd.get_text(strip=True).lower().replace(":", "")
                        val = ds.get_text(strip=True)
                        for k, field in luoc_do_mapping.items():
                            if k == raw_key:
                                if val and len(val) > 1:
                                    if field == "linh_vuc":
                                        metadata["linh_vuc"] = val
                                        metadata["nganh"] = val
                                    else:
                                        metadata[field] = val
                                    # logger.info(f"  -> {field} (from LuocDo): {val}")
                                break

            return metadata
        except Exception as e:
            logger.error(f"Error parsing document {url}: {e}")
            return None

    def scrape_content_only(self, url: str) -> Optional[str]:
        """
        Fetch only the main content HTML of a document.
        Useful for backfilling missing content while preserving existing metadata.
        """
        logger.info(f"Scraping content only: {url}")
        soup = self.get_page(url)
        if not soup:
            return None

        content_div = soup.select_one("#divNoiDung") or soup.select_one(".content1")
        return str(content_div) if content_div else ""

    def crawl(self, keywords: List[str], prefix: str = "test_"):
        """Crawl a list of keywords and save to parquet."""
        all_docs = []
        doc_count = 0
        
        for kw in keywords:
            urls = self.search_documents(kw)
            for url in urls:
                doc = self.scrape_document_detail(url, kw)
                if doc:
                    all_docs.append(doc)
                    doc_count += 1
                
                # Sleep between requests to be polite
                time.sleep(1)

                # Every 5 documents, take a longer break
                if doc_count > 0 and doc_count % 5 == 0:
                    logger.info("Reached 5 documents. Resting for 5 seconds...")
                    time.sleep(5)

        if all_docs:
            self.save_to_parquet(all_docs, prefix=prefix)
        else:
            logger.warning("No documents found for the given keywords.")

    def save_to_parquet(self, docs: List[Dict], prefix: str = "test_"):
        df = pd.DataFrame(docs)
        
        # All 17 metadata fields + url
        metadata_cols = [
            "id", "title", "so_ky_hieu", "ngay_ban_hanh", "loai_van_ban", 
            "ngay_co_hieu_luc", "ngay_het_hieu_luc", "nguon_thu_thap", 
            "ngay_dang_cong_bao", "nganh", "linh_vuc", "co_quan_ban_hanh", 
            "chuc_danh", "nguoi_ky", "pham_vi", "thong_tin_ap_dung", 
            "tinh_trang_hieu_luc", "url"
        ]
        content_cols = ["id", "content_html"]

        meta_df = df[metadata_cols]
        content_df = df[content_cols]

        meta_path = os.path.join(self.data_dir, f"{prefix}metadata.parquet")
        content_path = os.path.join(self.data_dir, f"{prefix}content.parquet")

        # Handle incremental saving: merge with existing if files exist
        if os.path.exists(meta_path):
            try:
                old_meta = pd.read_parquet(meta_path)
                meta_df = pd.concat([old_meta, meta_df]).drop_duplicates(subset=["id"], keep="last")
            except Exception as e:
                logger.warning(f"Could not merge with existing metadata: {e}")

        if os.path.exists(content_path):
            try:
                old_content = pd.read_parquet(content_path)
                content_df = pd.concat([old_content, content_df]).drop_duplicates(subset=["id"], keep="last")
            except Exception as e:
                logger.warning(f"Could not merge with existing content: {e}")

        meta_df.to_parquet(meta_path, index=False)
        content_df.to_parquet(content_path, index=False)
        logger.info(f"Cumulative save: {len(meta_df)} total documents in {self.data_dir} ({prefix}files)")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Crawl legal documents from thuvienphapluat.vn')
    parser.add_argument('--keywords', nargs='+', default=["88/2025/QH15", "Bộ luật dân sự 2015"], help='List of keywords or document numbers to search')
    parser.add_argument('--prefix', default="test_", help='Prefix for output parquet files')
    
    args = parser.parse_args()

    crawler = ThuVienPhapLuatCrawler()
    crawler.crawl(args.keywords, prefix=args.prefix)
