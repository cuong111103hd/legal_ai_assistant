"""
relation_extractor.py
---------------------
Trích xuất quan hệ pháp lý cấp văn bản (DOCUMENT level) từ preamble/tiêu đề.

Các loại quan hệ:
  SUPPLEMENTS  — sửa đổi, bổ sung
  REPLACES     — thay thế
  REVOKES      — bãi bỏ, hủy bỏ
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Vietnamese legal document numbers:  12/2024/QH15, 101/2015/NĐ-CP, 36/2021/TT-BGDĐT …
_DOC_NUMBER = re.compile(
    r'\b(\d{1,3}/\d{4}/'
    r'(?:QH\d+|NĐ-CP|TT-[\w-]+|QĐ-TTg|CT-TTg|UBND|HĐND|'
    r'BTC|BTP|BTNMT|BCT|BYT|BGDĐT|BLĐTBXH|BQP|BNV|BKHCN|BKHĐT|BGTVT|BNNPTNT|BTTTT|BVHTTDL|BXD|BCT|BVHTT))'
    r'\b',
    re.IGNORECASE,
)

# Relation keywords → type (checked in order; first match wins)
_RELATION_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'thay\s+thế',               re.IGNORECASE), 'REPLACES'),
    (re.compile(r'bãi\s+bỏ|huỷ\s+bỏ|hủy\s+bỏ', re.IGNORECASE), 'REVOKES'),
    (re.compile(r'sửa\s+đổi|bổ\s+sung',     re.IGNORECASE), 'SUPPLEMENTS'),
]

# Pattern trích xuất Điều/Khoản:
# Ưu tiên "khoản X Điều Y" trước, sau đó "Điều Y khoản X", cuối cùng chỉ "Điều Y"
# Không bắt điểm/tiết vì chunking không chia đến cấp đó
_ARTICLE_CLAUSE = re.compile(
    r'(?:khoản\s+(\d+)\s+)?[Đđ]iều\s+(\d+)(?:\s+khoản\s+(\d+))?',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class LegalRelation:
    source_doc_id: str
    source_number: str
    target_number: str
    relation_type: str
    level: str = "DOCUMENT"
    # Source article-level fields
    source_article: Optional[str] = None
    source_clause: Optional[str] = None
    # Article-level fields (None = doc-level only, no specific article targeted)
    target_article: Optional[str] = None   # e.g. "Điều 10"
    target_clause: Optional[str] = None    # e.g. "khoản 2"


# ---------------------------------------------------------------------------
# Core extraction helpers
# ---------------------------------------------------------------------------

def _extract_preamble(html_content: str, max_chars: int = 800) -> str:
    """
    Lấy phần văn bản đầu của HTML (trước khi gặp "Điều 1").
    """
    if not html_content:
        return ""

    text = BeautifulSoup(html_content, "html.parser").get_text(" ", strip=True)
    
    # Cắt nội dung ngay trước chữ "Điều 1"
    match = re.search(r'\bĐiều\s+1\b', text, re.IGNORECASE)
    if match:
        text = text[:match.start()]
        
    return text[:max_chars]


def _detect_relation_type(text: str) -> Optional[str]:
    """
    Return the FIRST relation type keyword found in text, or None.
    Prioritizes keywords appearing EARLIER in the text.
    """
    # Bỏ qua các cụm từ bị động (được sửa đổi, được bổ sung)
    passive_pattern = r'được\s+(?:sửa\s+đổi|bổ\s+sung)(?:[\s,]+(?:và\s+)?(?:sửa\s+đổi|bổ\s+sung))*'
    clean_text = re.sub(passive_pattern, '', text, flags=re.IGNORECASE)
    
    matches = []
    for pattern, rel_type in _RELATION_RULES:
        m = pattern.search(clean_text)
        if m:
            matches.append((m.start(), rel_type))
    
    if not matches:
        return None
        
    # Trả về loại quan hệ xuất hiện sớm nhất trong văn bản
    matches.sort()
    return matches[0][1]


def _extract_doc_numbers(text: str, exclude: str = "") -> list[str]:
    """Find all legal document numbers in text, excluding source's own number."""
    norm_exclude = exclude.strip()
    found = []
    for m in _DOC_NUMBER.finditer(text):
        num = m.group(1)
        if num != norm_exclude:
            found.append(num)
    return found


def _extract_article_clause(text: str, start_pos: int = 0) -> tuple[Optional[str], Optional[str]]:
    """
    Tìm cặp (Điều, Khoản) đầu tiên trong text bắt đầu từ start_pos.
    Trả về ("Điều X", "khoản Y") hoặc ("Điều X", None) nếu không có khoản.
    Không bắt điểm/tiết vì chunking không chia đến cấp đó.

    Pattern nhận dạng:
      - "khoản 2 Điều 10"  → ("Điều 10", "khoản 2")
      - "Điều 10 khoản 2"  → ("Điều 10", "khoản 2")
      - "Điều 10"          → ("Điều 10", None)
    """
    search_text = text[start_pos:]
    m = _ARTICLE_CLAUSE.search(search_text)
    if not m:
        return None, None
def _verb_to_rel_type(verb: str) -> str:
    v = verb.lower()
    if re.search(r'thay\s+thế', v): return 'REPLACES'
    if re.search(r'bãi\s+bỏ|huỷ\s+bỏ|hủy\s+bỏ', v): return 'REVOKES'
    return 'SUPPLEMENTS'


def parse_source_metadata(article_id: str) -> tuple[Optional[str], Optional[str]]:
    """Parse 'Khoản 1, Điều 2. Title' -> ('Điều 2', 'khoản 1')"""
    if not article_id or article_id == "Thông tin chung":
        return None, None
        
    source_clause = None
    source_article = None
    
    rest = article_id
    if article_id.lower().startswith("khoản"):
        parts = article_id.split(",", 1)
        if len(parts) == 2:
            source_clause = parts[0].strip().lower()  # "khoản 1"
            rest = parts[1].strip()
            
    m = re.match(r'(Điều\s+\d+)', rest, re.IGNORECASE)
    if m:
        source_article = m.group(1)
        # Chuẩn hóa chữ Đ viết hoa
        if source_article.startswith("đ"):
            source_article = "Đ" + source_article[1:]
            
    return source_article, source_clause


def _extract_dieu1_text(html_content: str, max_chars: int = 5000) -> str:
    """Lấy nội dung thân Điều 1 từ HTML (nơi liệt kê cụ thể điều/khoản sửa đổi)."""
    if not html_content:
        return ""
    text = BeautifulSoup(html_content, "html.parser").get_text(" ", strip=True)
    m1 = re.search(r'\bĐiều\s+1[\.\s]', text, re.IGNORECASE)
    if not m1:
        return ""
    rest = text[m1.end():]
    # Kết thúc tại Điều 2 (heading, không phải tham chiếu nội bộ)
    m2 = re.search(r'\bĐiều\s+2[\.\s]', rest, re.IGNORECASE)
    return rest[:m2.start() if m2 else max_chars]


def _extract_article_relations(
    dieu1_text: str,
    source_doc_id: str,
    source_number: str,
    target_number: str,
) -> list[LegalRelation]:
    """Parse thân Điều 1 → trả về tất cả article-level relations."""
    relations: list[LegalRelation] = []
    seen: set[tuple] = set()

    _VERB = re.compile(
        r'(sửa\s+đổi(?:\s*,\s*bổ\s+sung)?|bổ\s+sung|bãi\s+bỏ|hủy\s+bỏ|huỷ\s+bỏ|thay\s+thế)',
        re.IGNORECASE,
    )
    _PASSIVE_PREFIX = re.compile(r'được\s*$', re.IGNORECASE)

    for m_verb in _VERB.finditer(dieu1_text):
        # Bỏ qua bị động "được sửa đổi"
        if _PASSIVE_PREFIX.search(dieu1_text[:m_verb.start()].rstrip()):
            continue

        # Tìm Điều/Khoản trong cửa sổ 120 ký tự sau từ khóa
        window = dieu1_text[m_verb.end(): m_verb.end() + 120]
        m_art = _ARTICLE_CLAUSE.search(window)
        if not m_art:
            continue

        clause_before = m_art.group(1)
        article_num   = m_art.group(2)
        clause_after  = m_art.group(3)

        article = f"Điều {article_num}"
        clause_num = clause_before or clause_after
        clause = f"khoản {clause_num}" if clause_num else None

        key = (article, clause)
        if key in seen:
            continue
        seen.add(key)

        relations.append(LegalRelation(
            source_doc_id=source_doc_id,
            source_number=source_number,
            target_number=target_number,
            relation_type=_verb_to_rel_type(m_verb.group(1)),
            level="ARTICLE",
            target_article=article,
            target_clause=clause,
        ))

    return relations


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_PASSIVE_RE = re.compile(
    r'được\s+(?:sửa\s+đổi|bổ\s+sung)(?:[\s,]+(?:và\s+)?(?:sửa\s+đổi|bổ\s+sung))*',
    re.IGNORECASE,
)


def extract_relations(
    doc_id: str,
    doc_number: str,
    html_content: str,
    title: str,
    chunks: list[dict] | None = None,
) -> list[LegalRelation]:
    """
    Trích xuất TẤT CẢ quan hệ pháp lý từ một văn bản:
      - 1 quan hệ DOCUMENT-level từ preamble
      - N quan hệ ARTICLE-level từ thân Điều 1 (sử dụng chunks metadata nếu có)
    """
    preamble = _extract_preamble(html_content)
    combined = f"{title} {preamble}"

    # --- Doc-level: xác định văn bản nguồn & loại quan hệ ---
    anchor = "Quốc hội ban hành"
    m_anchor = re.search(re.escape(anchor), combined, re.IGNORECASE)
    target_text = combined[m_anchor.end():] if m_anchor else combined

    clean_target = _PASSIVE_RE.sub('', target_text)

    rel_matches = []
    for pattern, rel_type in _RELATION_RULES:
        m = pattern.search(clean_target)
        if m:
            rel_matches.append((m.start(), rel_type))
    if not rel_matches:
        return []

    rel_matches.sort()
    doc_rel_type = rel_matches[0][1]

    targets = _extract_doc_numbers(target_text, exclude=doc_number)
    if not targets:
        targets = _extract_doc_numbers(combined, exclude=doc_number)
    if not targets:
        logger.debug("doc %s: relation '%s' detected but no target doc number.", doc_id, doc_rel_type)
        return []

    target_number = targets[0]

    doc_rel = LegalRelation(
        source_doc_id=doc_id,
        source_number=doc_number,
        target_number=target_number,
        relation_type=doc_rel_type,
        level="DOCUMENT",
    )

    # --- Article-level: đọc thân Điều 1 ---
    article_rels = []
    if chunks is not None:
        # Dùng chunk metadata để trích xuất source_article/clause
        for chunk in chunks:
            art_id = str(chunk.get("article_id", ""))
            # Thường luật sửa đổi liệt kê ở Điều 1
            if "Điều 1" in art_id or "điều 1" in art_id.lower():
                rels = _extract_article_relations(chunk.get("content", ""), doc_id, doc_number, target_number)
                if rels:
                    s_art, s_clause = parse_source_metadata(art_id)
                    for r in rels:
                        r.source_article = s_art
                        r.source_clause = s_clause
                    article_rels.extend(rels)
    else:
        # Fallback dùng HTML nếu không có chunk (cho unit test)
        dieu1 = _extract_dieu1_text(html_content)
        article_rels = _extract_article_relations(dieu1, doc_id, doc_number, target_number) if dieu1 else []
        # Có thể mặc định source_article="Điều 1" cho fallback
        for r in article_rels:
            r.source_article = "Điều 1"

    return [doc_rel] + article_rels


def extract_relation(
    doc_id: str,
    doc_number: str,
    html_content: str,
    title: str,
) -> Optional[LegalRelation]:
    """Backward-compat wrapper: trả về quan hệ DOCUMENT-level đầu tiên."""
    rels = extract_relations(doc_id, doc_number, html_content, title)
    doc_rels = [r for r in rels if r.level == "DOCUMENT"]
    return doc_rels[0] if doc_rels else None


# ---------------------------------------------------------------------------
# CLI test (python -m src.relation_extractor)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    import sys

    # Allow running as module from project root
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

    from rich.console import Console
    from rich.table import Table

    console = Console()

    # ---- Inline unit tests ----
    _TEST_CASES = [
        {
            "title": "Sửa đổi, bổ sung một số điều của Bộ luật Tố tụng hình sự",
            "preamble": "Quốc hội ban hành Luật sửa đổi, bổ sung một số điều của Bộ luật Tố tụng hình sự số 101/2015/QH13.",
            "doc_number": "12/2021/QH15",
            "expected_type": "SUPPLEMENTS",
            "expected_target": "101/2015/QH13",
            "expected_article": None,
            "expected_clause": None,
        },
        {
            "title": "Thay thế Nghị định về xử phạt hành chính",
            "preamble": "Chính phủ ban hành Nghị định thay thế Nghị định số 15/2020/NĐ-CP.",
            "doc_number": "25/2023/NĐ-CP",
            "expected_type": "REPLACES",
            "expected_target": "15/2020/NĐ-CP",
            "expected_article": None,
            "expected_clause": None,
        },
        {
            "title": "Bãi bỏ một số văn bản quy phạm pháp luật",
            "preamble": "Bộ trưởng ban hành Thông tư bãi bỏ Thông tư số 36/2021/TT-BGDĐT.",
            "doc_number": "05/2024/TT-BGDĐT",
            "expected_type": "REVOKES",
            "expected_target": "36/2021/TT-BGDĐT",
            "expected_article": None,
            "expected_clause": None,
        },
        {
            "title": "Luật Doanh nghiệp",
            "preamble": "Quốc hội ban hành Luật Doanh nghiệp.",
            "doc_number": "59/2020/QH14",
            "expected_type": None,
            "expected_target": None,
            "expected_article": None,
            "expected_clause": None,
        },
        {
            "title": "Bị động (được sửa đổi)",
            "preamble": "được sửa đổi, bổ sung một số điều theo Nghị quyết số 51/2001/QH10",
            "doc_number": "99/2022/QH15",
            "expected_type": None,
            "expected_target": None,
            "expected_article": None,
            "expected_clause": None,
        },
        {
            "title": "Chủ động (sửa đổi)",
            "preamble": "Quốc hội ban hành Luật sửa đổi, bổ sung một số điều của Luật Di sản văn hóa số 28/2001/QH10.",
            "doc_number": "32/2009/QH12",
            "expected_type": "SUPPLEMENTS",
            "expected_target": "28/2001/QH10",
            "expected_article": None,
            "expected_clause": None,
        },
        # --- Article-level tests: HTML phải có thân Điều 1 ---
        {
            "title": "Sửa đổi khoản 2 Điều 10",
            "preamble": "<p>Quốc hội ban hành Luật sửa đổi Luật Lao động số 45/2019/QH14.</p>"
                        "<p>Điều 1. Sửa đổi Luật Lao động số 45/2019/QH14 như sau:</p>"
                        "<p>1. Sửa đổi khoản 2 Điều 10 như sau: nội dung mới.</p>"
                        "<p>Điều 2. Hiệu lực thi hành.</p>",
            "doc_number": "10/2022/QH15",
            "expected_type": "SUPPLEMENTS",
            "expected_target": "45/2019/QH14",
            "expected_article": "Điều 10",
            "expected_clause": "khoản 2",
        },
        {
            "title": "Bãi bỏ Điều 5",
            "preamble": "<p>Quốc hội ban hành Luật bãi bỏ một số điều của Luật Doanh nghiệp số 59/2020/QH14.</p>"
                        "<p>Điều 1. Bãi bỏ Luật Doanh nghiệp số 59/2020/QH14 như sau:</p>"
                        "<p>1. Bãi bỏ Điều 5.</p>"
                        "<p>Điều 2. Hiệu lực.</p>",
            "doc_number": "11/2023/QH15",
            "expected_type": "REVOKES",
            "expected_target": "59/2020/QH14",
            "expected_article": "Điều 5",
            "expected_clause": None,
        },
        {
            "title": "Sửa đổi Điều 3 khoản 1",
            "preamble": "<p>Quốc hội ban hành Luật sửa đổi Luật An ninh mạng số 24/2018/QH14.</p>"
                        "<p>Điều 1. Sửa đổi Luật An ninh mạng số 24/2018/QH14 như sau:</p>"
                        "<p>1. Sửa đổi Điều 3 khoản 1: nội dung mới.</p>"
                        "<p>Điều 2. Điều khoản thi hành.</p>",
            "doc_number": "15/2024/QH15",
            "expected_type": "SUPPLEMENTS",
            "expected_target": "24/2018/QH14",
            "expected_article": "Điều 3",
            "expected_clause": "khoản 1",
        },
    ]

    table = Table(title="Relation Extractor — Unit Tests", show_lines=True)
    table.add_column("Title (short)", style="cyan", max_width=30)
    table.add_column("Expected type→target", style="yellow", max_width=25)
    table.add_column("Expected article/clause", style="yellow", max_width=22)
    table.add_column("Got type→target", style="green", max_width=25)
    table.add_column("Got article/clause", style="green", max_width=22)
    table.add_column("Pass?", style="bold")

    all_passed = True
    for tc in _TEST_CASES:
        # Nếu preamble đã là HTML (có <p>) thì dùng trực tiếp, ngược lại wrap vào <p>
        raw = tc["preamble"]
        fake_html = raw if raw.startswith("<") else f"<p>{raw}</p>"
        exp_article = tc["expected_article"]
        exp_clause  = tc["expected_clause"]

        # Nếu test case có expected_article → dùng extract_relations, tìm ARTICLE-level match
        if exp_article is not None:
            all_rels = extract_relations(
                doc_id="test-id", doc_number=tc["doc_number"],
                html_content=fake_html, title=tc["title"],
            )
            art_rels = [r for r in all_rels if r.level == "ARTICLE"
                        and r.target_article == exp_article
                        and r.target_clause == exp_clause]
            result = art_rels[0] if art_rels else None
        else:
            result = extract_relation(
                doc_id="test-id", doc_number=tc["doc_number"],
                html_content=fake_html, title=tc["title"],
            )

        got_type    = result.relation_type  if result else None
        got_target  = result.target_number  if result else None
        got_article = result.target_article if result else None
        got_clause  = result.target_clause  if result else None

        passed = (
            got_type    == tc["expected_type"]    and
            got_target  == tc["expected_target"]  and
            got_article == exp_article and
            got_clause  == exp_clause
        )
        all_passed = all_passed and passed

        table.add_row(
            tc["title"][:30],
            f"{tc['expected_type']} → {tc['expected_target']}",
            f"{exp_article} / {exp_clause}",
            f"{got_type} → {got_target}",
            f"{got_article} / {got_clause}",
            "✅" if passed else "❌",
        )

    console.print(table)

    if all_passed:
        console.print("\n[bold green]All tests passed![/bold green]")
    else:
        console.print("\n[bold red]Some tests FAILED.[/bold red]")
        sys.exit(1)

    # ---- Live test on real data ----
    console.print("\n[bold cyan]Live test — extract_relations() on first 200 documents...[/bold cyan]")
    try:
        import pandas as pd

        meta_df = pd.read_parquet("data/raw/metadata.parquet")
        content_df = pd.read_parquet("data/raw/content.parquet")
        meta_df["id"] = meta_df["id"].astype(str)
        content_df["id"] = content_df["id"].astype(str)
        df = pd.merge(content_df, meta_df, on="id", how="left").head(200)

        live_table = Table(title="Live Extraction Results", show_lines=True)
        live_table.add_column("Source", style="dim", max_width=22)
        live_table.add_column("Level", style="white", max_width=9)
        live_table.add_column("Relation", style="yellow", max_width=12)
        live_table.add_column("Target doc", style="cyan", max_width=22)
        live_table.add_column("Article", style="magenta", max_width=10)
        live_table.add_column("Clause", style="blue", max_width=10)

        found = 0
        for _, row in df.iterrows():
            rels = extract_relations(
                doc_id=str(row.get("id", "")),
                doc_number=str(row.get("so_ky_hieu", "")),
                html_content=str(row.get("content_html", "")),
                title=str(row.get("title", "")),
            )
            for rel in rels:
                live_table.add_row(
                    rel.source_number,
                    rel.level,
                    rel.relation_type,
                    rel.target_number,
                    rel.target_article or "-",
                    rel.target_clause  or "-",
                )
                found += 1

        console.print(live_table)
        console.print(f"\nFound [bold blue]{found}[/bold blue] total relations in 200 documents.")
    except FileNotFoundError:
        console.print("[yellow]Parquet files not found — skipping live test.[/yellow]")

