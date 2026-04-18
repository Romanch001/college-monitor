"""
scraper.py — fetch pages, extract sections, find PDFs, compute diffs
"""
import os
import hashlib
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; COEPMonitor/2.0)"}


# ── Fetch ────────────────────────────────────────────────────────
def fetch_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


# ── Section extraction ───────────────────────────────────────────
def extract_sections(soup: BeautifulSoup, selectors: list) -> dict:
    """Return {label: cleaned_text} for each matched section + __full__."""
    sections = {}
    seen_ids = set()

    for selector, label in selectors:
        el = soup.select_one(selector)
        if el and id(el) not in seen_ids:
            seen_ids.add(id(el))
            text = _clean_text(el)
            if text:
                sections[label] = text

    # Strip noise then grab full text
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    sections["__full__"] = _clean_text(soup)
    return sections


def _clean_text(el) -> str:
    return "\n".join(
        line.strip()
        for line in el.get_text(separator="\n").splitlines()
        if line.strip()
    )


# ── PDF extraction ───────────────────────────────────────────────
def extract_pdfs(soup: BeautifulSoup, base_url: str) -> dict:
    """Return {absolute_url: link_label}."""
    pdfs = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().endswith(".pdf"):
            abs_url = urljoin(base_url, href)
            label = a.get_text(strip=True) or os.path.basename(urlparse(abs_url).path)
            pdfs[abs_url] = label
    return pdfs


# ── Download PDF ─────────────────────────────────────────────────
def download_pdf(url: str, max_bytes: int) -> tuple | None:
    """Return (bytes, size_str) or None if too large / failed."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        r.raise_for_status()
        content = b""
        for chunk in r.iter_content(65536):
            content += chunk
            if len(content) > max_bytes:
                return None
        return content, f"{len(content) / 1024:.0f} KB"
    except Exception as e:
        print(f"  [scraper] PDF download failed {url}: {e}")
        return None


# ── Keyword detection ────────────────────────────────────────────
def find_keywords(text: str, keywords: list) -> list:
    """Return list of keywords (case-insensitive) found in text."""
    lower = text.lower()
    return [kw for kw in keywords if kw.lower() in lower]


# ── Diff ─────────────────────────────────────────────────────────
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def compute_diff(old: str, new: str) -> dict:
    """Return {added: [...], removed: [...]} line lists."""
    old_set = set(old.splitlines())
    new_set = set(new.splitlines())
    return {
        "added":   [l for l in new.splitlines() if l.strip() and l not in old_set],
        "removed": [l for l in old.splitlines() if l.strip() and l not in new_set],
    }
