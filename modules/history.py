"""
history.py — change log (history.json), PDF archive, weekly digest builder
"""
import os
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse


HISTORY_FILE   = "history.json"
ARCHIVE_FOLDER = "archived_pdfs"


# ── Change log ───────────────────────────────────────────────────
def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def append_history(entry: dict):
    """
    entry = {
      timestamp, page_name, page_url,
      sections_changed, new_pdfs, keywords_found, ai_summary
    }
    """
    history = load_history()
    history.append(entry)
    # Keep last 500 entries
    if len(history) > 500:
        history = history[-500:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ── PDF archive ──────────────────────────────────────────────────
def archive_pdf(pdf_bytes: bytes, url: str, label: str) -> str:
    """Save PDF to archived_pdfs/ with a dated filename. Returns saved path."""
    os.makedirs(ARCHIVE_FOLDER, exist_ok=True)
    filename   = os.path.basename(urlparse(url).path) or "document.pdf"
    date_str   = datetime.now().strftime("%Y-%m-%d")
    safe_label = "".join(c if c.isalnum() or c in "._- " else "_" for c in label)[:40]
    dest       = os.path.join(ARCHIVE_FOLDER, f"{date_str}_{safe_label}_{filename}")
    with open(dest, "wb") as f:
        f.write(pdf_bytes)
    print(f"  [archive] Saved: {dest}")
    return dest


# ── Weekly digest ────────────────────────────────────────────────
def build_weekly_digest_html() -> str:
    """Read history.json and build HTML digest for the past 7 days."""
    history = load_history()
    cutoff  = datetime.now() - timedelta(days=7)

    recent = [
        e for e in history
        if datetime.fromisoformat(e["timestamp"]) >= cutoff
    ]

    if not recent:
        return "<p>No changes detected in the past 7 days.</p>"

    # Group by page
    by_page: dict[str, list] = {}
    for e in recent:
        by_page.setdefault(e["page_name"], []).append(e)

    def _esc(s):
        return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

    rows = ""
    for page, entries in by_page.items():
        rows += f"""
        <tr style="background:#eaf2ff">
          <td colspan="4" style="padding:8px 12px;font-weight:bold;color:#1a5276">
            📄 {_esc(page)} — {len(entries)} change(s)
          </td>
        </tr>"""
        for e in entries:
            ts       = datetime.fromisoformat(e["timestamp"]).strftime("%d %b, %I:%M %p")
            sections = ", ".join(e.get("sections_changed", [])) or "—"
            n_pdfs   = len(e.get("new_pdfs", {}))
            kws      = ", ".join(e.get("keywords_found", [])) or "—"
            summary  = e.get("ai_summary") or "—"
            rows += f"""
        <tr style="border-bottom:1px solid #eee">
          <td style="padding:6px 12px;white-space:nowrap;color:#555">{ts}</td>
          <td style="padding:6px 12px">{_esc(sections)}</td>
          <td style="padding:6px 12px;text-align:center">{n_pdfs}</td>
          <td style="padding:6px 12px;font-size:12px;color:#555">{_esc(summary[:120])}</td>
        </tr>"""

    # Count totals
    total_changes = len(recent)
    total_pdfs    = sum(len(e.get("new_pdfs", {})) for e in recent)
    all_kws: dict[str, int] = {}
    for e in recent:
        for k in e.get("keywords_found", []):
            all_kws[k] = all_kws.get(k, 0) + 1
    top_kws = sorted(all_kws, key=lambda k: -all_kws[k])[:8]

    kw_pills = "".join(
        f'<span style="background:#d6eaf8;color:#1a5276;border-radius:12px;'
        f'padding:3px 10px;font-size:12px;margin:2px;display:inline-block">'
        f'{_esc(k)} ({all_kws[k]})</span>'
        for k in top_kws
    ) or "<em>None</em>"

    week_start = (datetime.now() - timedelta(days=6)).strftime("%d %b")
    week_end   = datetime.now().strftime("%d %b %Y")

    return f"""
    <div style="font-family:Arial,sans-serif;max-width:700px;margin:auto">
      <div style="background:#154360;color:#fff;padding:18px 24px;border-radius:8px 8px 0 0">
        <h2 style="margin:0">📊 COEP Monitor — Weekly Digest</h2>
        <p style="margin:6px 0 0;opacity:0.8;font-size:13px">{week_start} – {week_end}</p>
      </div>

      <div style="display:flex;gap:0;border-bottom:2px solid #d6eaf8">
        <div style="flex:1;padding:16px 20px;text-align:center;border-right:1px solid #eee">
          <div style="font-size:28px;font-weight:bold;color:#1a5276">{total_changes}</div>
          <div style="font-size:12px;color:#888">Total changes</div>
        </div>
        <div style="flex:1;padding:16px 20px;text-align:center;border-right:1px solid #eee">
          <div style="font-size:28px;font-weight:bold;color:#6c3483">{total_pdfs}</div>
          <div style="font-size:12px;color:#888">New PDFs</div>
        </div>
        <div style="flex:1;padding:16px 20px;text-align:center">
          <div style="font-size:28px;font-weight:bold;color:#1a7a1a">{len(by_page)}</div>
          <div style="font-size:12px;color:#888">Pages affected</div>
        </div>
      </div>

      <div style="padding:16px 20px">
        <h3 style="color:#1a5276;margin:0 0 8px">Top keywords this week</h3>
        {kw_pills}
      </div>

      <div style="padding:0 20px 20px">
        <h3 style="color:#1a5276;margin:0 0 8px">Change log</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <tr style="background:#154360;color:#fff">
            <th style="padding:8px 12px;text-align:left">Time</th>
            <th style="padding:8px 12px;text-align:left">Section(s)</th>
            <th style="padding:8px 12px;text-align:center">PDFs</th>
            <th style="padding:8px 12px;text-align:left">AI Summary</th>
          </tr>
          {rows}
        </table>
      </div>

      <div style="background:#f2f3f4;padding:12px 24px;font-size:12px;color:#888;
                  border-radius:0 0 8px 8px;border-top:1px solid #e5e8e8">
        Automated weekly digest · GitHub Actions · ₹0 cost
      </div>
    </div>"""
