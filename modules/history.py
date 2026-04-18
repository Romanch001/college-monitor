"""
history.py — Change log (history.json) + weekly digest builder
"""
import os, json, html
from datetime import datetime, timedelta

HISTORY_FILE = "history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f: return json.load(f)
    return []

def append_history(entry):
    history = load_history()
    history.append(entry)
    if len(history) > 1000: history = history[-1000:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def build_weekly_digest_html():
    history = load_history()
    cutoff  = datetime.now() - timedelta(days=7)
    recent  = [e for e in history if datetime.fromisoformat(e["timestamp"]) >= cutoff]
    if not recent:
        return "<p>No changes detected in the past 7 days.</p>"

    by_page = {}
    for e in recent:
        by_page.setdefault(e["page_name"], []).append(e)

    def _e(s): return html.escape(str(s))

    rows = ""
    for page, entries in by_page.items():
        rows += f'<tr style="background:#eaf2ff"><td colspan="5" style="padding:8px 12px;font-weight:bold;color:#1a5276">📄 {_e(page)} — {len(entries)} change(s)</td></tr>'
        for e in entries:
            ts      = datetime.fromisoformat(e["timestamp"]).strftime("%d %b, %I:%M %p")
            sec     = ", ".join(e.get("sections_changed", []))[:60] or "—"
            n_pdfs  = len(e.get("new_pdfs", {}))
            kws     = ", ".join(e.get("keywords_found", []))[:60] or "—"
            score   = e.get("importance_score", "—")
            summary = (e.get("ai_summary") or "—")[:120]
            rows += f"""<tr style="border-bottom:1px solid #eee">
              <td style="padding:6px 12px;white-space:nowrap;color:#555">{ts}</td>
              <td style="padding:6px 12px;font-weight:bold;text-align:center">{score}</td>
              <td style="padding:6px 12px">{_e(sec)}</td>
              <td style="padding:6px 12px;text-align:center">{n_pdfs}</td>
              <td style="padding:6px 12px;font-size:12px;color:#555">{_e(summary)}</td></tr>"""

    total_changes = len(recent)
    total_pdfs    = sum(len(e.get("new_pdfs", {})) for e in recent)
    kw_freq = {}
    for e in recent:
        for k in e.get("keywords_found", []):
            kw_freq[k] = kw_freq.get(k, 0) + 1
    top_kws = sorted(kw_freq, key=lambda k: -kw_freq[k])[:8]
    kw_pills = "".join(
        f'<span style="background:#d6eaf8;color:#1a5276;border-radius:12px;padding:3px 10px;font-size:12px;margin:2px;display:inline-block">{_e(k)} ({kw_freq[k]})</span>'
        for k in top_kws
    ) or "<em>None</em>"

    week_start = (datetime.now() - timedelta(days=6)).strftime("%d %b")
    week_end   = datetime.now().strftime("%d %b %Y")

    return f"""<div style="font-family:Arial,sans-serif;max-width:700px;margin:auto">
      <div style="background:#154360;color:#fff;padding:18px 24px;border-radius:8px 8px 0 0">
        <h2 style="margin:0">📊 COEP Monitor — Weekly Digest</h2>
        <p style="margin:6px 0 0;opacity:0.8;font-size:13px">{week_start} – {week_end}</p>
      </div>
      <div style="display:flex;border-bottom:2px solid #d6eaf8">
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
        <h3 style="color:#1a5276;margin:0 0 8px">Top keywords</h3>{kw_pills}
      </div>
      <div style="padding:0 20px 20px">
        <h3 style="color:#1a5276;margin:0 0 8px">Change log</h3>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
          <tr style="background:#154360;color:#fff">
            <th style="padding:8px 12px;text-align:left">Time</th>
            <th style="padding:8px 12px;text-align:center">Score</th>
            <th style="padding:8px 12px;text-align:left">Sections</th>
            <th style="padding:8px 12px;text-align:center">PDFs</th>
            <th style="padding:8px 12px;text-align:left">AI Summary</th>
          </tr>{rows}
        </table>
      </div>
      <div style="background:#f2f3f4;padding:12px 24px;font-size:12px;color:#888;border-radius:0 0 8px 8px">
        Automated weekly digest · GitHub Actions · ₹0
      </div>
    </div>"""
