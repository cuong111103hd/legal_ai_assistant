"""
Vietnamese text processing utilities for legal documents.
Handles: HTML cleaning, Unicode normalization, article extraction, tokenization.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Unicode normalisation
# ---------------------------------------------------------------------------

def normalize_vietnamese(text: str) -> str:
    """
    Normalize Vietnamese text to NFC Unicode form.
    This ensures consistent representation of tone marks (dấu).
    Example: tổ + ̉  →  tổ  (composed form)
    """
    return unicodedata.normalize("NFC", text)


# ---------------------------------------------------------------------------
# HTML → plain text
# ---------------------------------------------------------------------------

def clean_html(html_content: str) -> str:
    """
    Strip HTML tags and return clean text.
    Preserves paragraph structure with newlines.
    """
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove script / style elements
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Get text with newline separation for block elements
    text = soup.get_text(separator="\n")

    # Collapse excessive whitespace while keeping structure
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(line for line in lines if line)

    return normalize_vietnamese(text)


# ---------------------------------------------------------------------------
# Article / clause extraction
# ---------------------------------------------------------------------------

# Matches "Điều 168" or "Điều 168." at the start of a line or after newline
_ARTICLE_PATTERN = re.compile(
    r"Điều\s+(\d+[a-zA-Z]?)",
    re.UNICODE,
)

# Matches "Khoản 1" patterns
_CLAUSE_PATTERN = re.compile(
    r"Khoản\s+(\d+[a-zA-Z]?)",
    re.UNICODE,
)


def extract_article_id(text: str) -> str:
    """
    Extract the first 'Điều X' reference from text.
    Returns e.g. 'Điều 168' or '' if not found.
    """
    m = _ARTICLE_PATTERN.search(text)
    return f"Điều {m.group(1)}" if m else ""


def extract_clause_id(text: str) -> str:
    """
    Extract the first 'Khoản X' reference from text.
    Returns e.g. 'Khoản 1' or '' if not found.
    """
    m = _CLAUSE_PATTERN.search(text)
    return f"Khoản {m.group(1)}" if m else ""


def extract_all_article_refs(text: str) -> list[str]:
    """Extract all 'Điều X' references present in the text."""
    return [f"Điều {m.group(1)}" for m in _ARTICLE_PATTERN.finditer(text)]


def chunk_contract_by_article(text: str) -> list[dict[str, str]]:
    """
    Split a contract into chunks based on "Điều" (Article) headers.
    Returns a list of dicts: {"title": "Điều X", "content": "..."}
    """
    # Regex to find "Điều X" at start of lines
    pattern = re.compile(r"^(Điều\s+\d+[a-zA-Z]*[:\.]?.*)$", re.MULTILINE | re.IGNORECASE)
    
    matches = list(pattern.finditer(text))
    if not matches:
        # Fallback if no "Điều" found: return the whole text as one chunk
        return [{"title": "Toàn văn hợp đồng", "content": text.strip()}]
    
    chunks = []
    for i in range(len(matches)):
        start_idx = matches[i].start()
        end_idx = matches[i+1].start() if i + 1 < len(matches) else len(text)
        
        chunk_text = text[start_idx:end_idx].strip()
        title = matches[i].group(1).split("\n")[0].strip()
        
        # Clean the title (remove trailing dots/colons)
        title = re.sub(r"[:\.]$", "", title)
        
        chunks.append({"title": title, "content": chunk_text})
        
    return chunks


# ---------------------------------------------------------------------------
# Vietnamese tokenisation (for BM25)
# ---------------------------------------------------------------------------

# Pattern to strip punctuation but keep Vietnamese characters
_TOKEN_PATTERN = re.compile(r"[^\w\sàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]", re.UNICODE | re.IGNORECASE)

# Common Vietnamese stop words for legal text (minimal set — keeps legal terms)
_STOP_WORDS: set[str] = {
    "và", "của", "là", "có", "không", "được", "trong", "cho", "các",
    "với", "để", "từ", "này", "đó", "theo", "về", "đã", "sẽ",
    "do", "khi", "nếu", "hoặc", "nhưng", "cũng", "tại", "bởi",
    "một", "những", "thì", "mà", "hay", "như", "vào", "ra",
    "lên", "xuống", "trên", "dưới", "sau", "trước",
}


def tokenize_vietnamese(text: str, remove_stopwords: bool = True) -> list[str]:
    """
    Simple whitespace-based tokenizer for Vietnamese.
    Vietnamese words are naturally space-separated, so this works well
    for BM25 ranking on legal text.

    Args:
        text: Input Vietnamese text.
        remove_stopwords: Whether to remove common stop words.

    Returns:
        List of lowercase tokens.
    """
    text = normalize_vietnamese(text.lower())
    text = _TOKEN_PATTERN.sub(" ", text)
    tokens = text.split()

    if remove_stopwords:
        tokens = [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]

    return tokens


# ---------------------------------------------------------------------------
# Document number extraction
# ---------------------------------------------------------------------------

_DOC_NUMBER_PATTERN = re.compile(
    r"(\d+/\d{4}/[A-ZĐ\-]+(?:/[A-ZĐ\-]+)*)",
    re.UNICODE,
)


def extract_document_number(text: str) -> str:
    """
    Extract Vietnamese legal document number (Số hiệu).
    E.g. '45/2019/QH14', '145/2020/NĐ-CP'
    """
    m = _DOC_NUMBER_PATTERN.search(text)
    return m.group(1) if m else ""
