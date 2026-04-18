"""
pdf_intelligence.py — PDF search, version comparison, timetable detection
All local processing — no external services needed.
"""
import os, hashlib, json
from urllib.parse import urlparse

ARCHIVE_FOLDER  = "archived_pdfs"
PDF_INDEX_FILE  = "pdf_index.json"

TIMETABLE_KEYWORDS = [
    "timetable", "time table", "schedule", "lecture schedule",
    "class schedule", "exam schedule", "slot", "period"
]

# ── PDF index (url → {filename, hash, archived_path, date}) ─────
def load_pdf_index():
    if os.path.exists(PDF_INDEX_FILE):
        with open(PDF_INDEX_FILE, "r") as f:
            return json.load(f)
    return {}

def save_pdf_index(index):
    with open(PDF_INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)

# ── Archive PDF ──────────────────────────────────────────────────
def archive_pdf(pdf_bytes, url, label, date_str):
    os.makedirs(ARCHIVE_FOLDER, exist_ok=True)
    filename   = os.path.basename(urlparse(url).path) or "document.pdf"
    safe_label = "".join(c if c.isalnum() or c in "-_." else "_" for c in label)[:40]
    dest       = os.path.join(ARCHIVE_FOLDER, f"{date_str}_{safe_label}_{filename}")
    with open(dest, "wb") as f:
        f.write(pdf_bytes)

    # Update index
    index = load_pdf_index()
    prev_hash = index.get(url, {}).get("hash")
    new_hash  = hashlib.md5(pdf_bytes).hexdigest()
    index[url] = {
        "filename":      filename,
        "label":         label,
        "hash":          new_hash,
        "prev_hash":     prev_hash,
        "archived_path": dest,
        "date":          date_str,
    }
    save_pdf_index(index)
    print(f"  [pdf] Archived: {dest}")
    return dest, prev_hash, new_hash

# ── Detect if PDF is a timetable ─────────────────────────────────
def is_timetable(filename, label):
    combined = (filename + " " + label).lower()
    return any(kw in combined for kw in TIMETABLE_KEYWORDS)

# ── Check if PDF is a new version of existing file ───────────────
def get_previous_version(url):
    """Returns previous pdf_bytes from archive if same URL was seen before, else None."""
    index = load_pdf_index()
    entry = index.get(url)
    if not entry or not entry.get("archived_path"):
        return None
    prev_path = entry["archived_path"]
    if os.path.exists(prev_path):
        with open(prev_path, "rb") as f:
            return f.read()
    return None

# ── Compare two PDF versions (text-level diff) ───────────────────
def compare_pdf_versions(old_bytes, new_bytes):
    """
    Extract text from both PDFs and return a simple diff summary.
    Uses pdfminer if available, falls back to raw byte comparison.
    """
    try:
        from pdfminer.high_level import extract_text
        from io import BytesIO
        old_text = extract_text(BytesIO(old_bytes)) or ""
        new_text = extract_text(BytesIO(new_bytes)) or ""
    except ImportError:
        # Fallback: just report size change
        diff_kb = (len(new_bytes) - len(old_bytes)) / 1024
        sign    = "+" if diff_kb > 0 else ""
        return f"File size changed by {sign}{diff_kb:.1f} KB (install pdfminer.six for text diff)"

    old_lines = set(old_text.splitlines())
    new_lines = set(new_text.splitlines())
    added   = [l.strip() for l in new_lines - old_lines if l.strip()][:15]
    removed = [l.strip() for l in old_lines - new_lines if l.strip()][:15]

    parts = []
    if added:   parts.append("ADDED:\n"   + "\n".join(added))
    if removed: parts.append("REMOVED:\n" + "\n".join(removed))
    return "\n\n".join(parts) or "Content rearranged (no clear add/remove)"

# ── Search archived PDFs ─────────────────────────────────────────
def search_pdfs(query):
    """
    Search all archived PDFs for query string.
    Returns list of {path, label, date, matches: [str]}
    """
    query_lower = query.lower()
    results     = []
    index       = load_pdf_index()

    if not os.path.exists(ARCHIVE_FOLDER):
        return []

    for url, meta in index.items():
        path = meta.get("archived_path", "")
        if not os.path.exists(path):
            continue
        try:
            # Try text extraction
            try:
                from pdfminer.high_level import extract_text
                with open(path, "rb") as f:
                    text = extract_text(f) or ""
            except ImportError:
                # Fallback: search filename and label only
                text = meta.get("label", "") + " " + meta.get("filename", "")

            matches = [
                line.strip() for line in text.splitlines()
                if query_lower in line.lower() and line.strip()
            ][:5]

            if matches or query_lower in meta.get("label", "").lower():
                results.append({
                    "path":    path,
                    "label":   meta.get("label", ""),
                    "date":    meta.get("date", ""),
                    "url":     url,
                    "matches": matches,
                })
        except Exception as e:
            print(f"  [pdf_search] Error reading {path}: {e}")

    return results
