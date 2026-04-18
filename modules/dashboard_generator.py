"""
dashboard_generator.py — Generate docs/index.html (served via GitHub Pages)
Enable: repo Settings → Pages → Source: main branch, /docs folder
Your dashboard URL: https://romanch001.github.io/college-monitor/
"""
import os, json, html
from datetime import datetime, timedelta

HISTORY_FILE    = "history.json"
DEADLINES_FILE  = "deadlines.json"
PDF_INDEX_FILE  = "pdf_index.json"
OUTPUT_FILE     = "docs/index.html"

def _load(path):
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    return [] if path != PDF_INDEX_FILE else {}

def _esc(s): return html.escape(str(s))

def generate_dashboard():
    os.makedirs("docs", exist_ok=True)
    history   = _load(HISTORY_FILE)
    deadlines = _load(DEADLINES_FILE)
    pdf_index = _load(PDF_INDEX_FILE)

    now      = datetime.now()
    week_ago = now - timedelta(days=7)
    recent   = [e for e in history if datetime.fromisoformat(e["timestamp"]) >= week_ago]
    total_changes = len(history)
    total_pdfs    = len(pdf_index)
    week_changes  = len(recent)

    # Upcoming deadlines
    upcoming_dl = []
    for dl in deadlines:
        from modules.calendar_manager import _try_parse_date
        parsed = _try_parse_date(dl.get("date_str",""))
        if parsed:
            days = (parsed - now).days
            if -1 <= days <= 30:
                upcoming_dl.append({**dl, "days_left": days})
    upcoming_dl.sort(key=lambda d: d.get("days_left", 99))

    # Recent changes (last 20)
    recent_items = list(reversed(history[-20:]))

    # Keyword frequency
    kw_freq = {}
    for e in history:
        for k in e.get("keywords_found", []):
            kw_freq[k] = kw_freq.get(k, 0) + 1
    top_kws = sorted(kw_freq, key=lambda k: -kw_freq[k])[:12]

    # Build HTML
    def stat_card(val, label, color):
        return f"""<div class="stat-card" style="border-top:3px solid {color}">
          <div class="stat-val" style="color:{color}">{val}</div>
          <div class="stat-label">{label}</div></div>"""

    def deadline_row(dl):
        days  = dl.get("days_left", 0)
        color = "#c0392b" if days <= 1 else "#e67e22" if days <= 3 else "#2980b9"
        badge = "TODAY" if days <= 0 else f"{days}d"
        return f"""<tr>
          <td><span class="badge" style="background:{color}">{_esc(badge)}</span></td>
          <td>{_esc(dl.get('date_str',''))}</td>
          <td>{_esc(dl.get('description','')[:70])}</td>
          <td><span class="type-badge">{_esc(dl.get('type',''))}</span></td>
          <td><a href="{_esc(dl.get('page_url',''))}" target="_blank">{_esc(dl.get('page_name',''))}</a></td>
        </tr>"""

    def change_row(e):
        ts      = datetime.fromisoformat(e["timestamp"]).strftime("%d %b %H:%M")
        score   = e.get("importance_score", "–")
        color   = "#c0392b" if str(score).isdigit() and int(score) >= 8 \
                  else "#e67e22" if str(score).isdigit() and int(score) >= 5 else "#27ae60"
        sections = ", ".join(e.get("sections_changed", []))[:60]
        summary  = (e.get("ai_summary") or "")[:100]
        n_pdfs   = len(e.get("new_pdfs", {}))
        kws      = ", ".join(e.get("keywords_found", [])[:4])
        return f"""<tr>
          <td style="white-space:nowrap;color:#666">{ts}</td>
          <td><a href="{_esc(e.get('page_url',''))}" target="_blank">{_esc(e.get('page_name',''))}</a></td>
          <td style="color:{color};font-weight:bold;text-align:center">{score}</td>
          <td style="font-size:12px;color:#555">{_esc(sections)}</td>
          <td style="font-size:12px">{_esc(summary)}</td>
          <td style="text-align:center">{"📎 "+str(n_pdfs) if n_pdfs else "–"}</td>
          <td style="font-size:11px;color:#888">{_esc(kws)}</td>
        </tr>"""

    kw_pills = "".join(
        f'<span class="kw-pill">{_esc(k)} <b>{kw_freq[k]}</b></span>'
        for k in top_kws
    )

    deadline_rows = "".join(deadline_row(dl) for dl in upcoming_dl[:15]) or \
                    "<tr><td colspan='5' style='text-align:center;color:#aaa'>No upcoming deadlines tracked yet.</td></tr>"
    change_rows   = "".join(change_row(e) for e in recent_items) or \
                    "<tr><td colspan='7' style='text-align:center;color:#aaa'>No changes logged yet.</td></tr>"

    updated_at = now.strftime("%d %b %Y, %I:%M %p IST")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>COEP Monitor Dashboard</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
         background:#f0f2f5; color:#333 }}
  header {{ background:linear-gradient(135deg,#154360,#1a5276);
            color:#fff; padding:20px 32px; display:flex;
            justify-content:space-between; align-items:center }}
  header h1 {{ font-size:22px; font-weight:600 }}
  header .sub {{ font-size:12px; opacity:0.75; margin-top:4px }}
  .updated {{ font-size:11px; opacity:0.7 }}
  .container {{ max-width:1200px; margin:0 auto; padding:24px 16px }}
  .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:24px }}
  .stat-card {{ background:#fff; padding:20px; border-radius:10px;
                box-shadow:0 1px 4px rgba(0,0,0,.08); text-align:center }}
  .stat-val {{ font-size:32px; font-weight:700; line-height:1 }}
  .stat-label {{ font-size:12px; color:#888; margin-top:6px }}
  .card {{ background:#fff; border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.08);
           margin-bottom:24px; overflow:hidden }}
  .card-header {{ background:#f8f9fa; padding:14px 20px; border-bottom:1px solid #eee;
                  font-weight:600; font-size:14px; color:#1a5276; display:flex;
                  justify-content:space-between; align-items:center }}
  table {{ width:100%; border-collapse:collapse; font-size:13px }}
  th {{ background:#f8f9fa; padding:10px 12px; text-align:left;
        color:#555; font-weight:600; border-bottom:2px solid #eee }}
  td {{ padding:9px 12px; border-bottom:1px solid #f0f0f0; vertical-align:top }}
  tr:last-child td {{ border-bottom:none }}
  tr:hover td {{ background:#fafbfc }}
  .badge {{ color:#fff; font-size:11px; font-weight:700; padding:2px 8px;
            border-radius:12px; display:inline-block }}
  .type-badge {{ background:#eef;color:#556;font-size:11px;
                 padding:2px 7px;border-radius:4px;border:1px solid #dde }}
  .kw-pills {{ padding:16px 20px; display:flex; flex-wrap:wrap; gap:8px }}
  .kw-pill {{ background:#eaf2ff; color:#1a5276; border:1px solid #aed6f1;
              border-radius:14px; padding:4px 12px; font-size:12px }}
  a {{ color:#2471a3; text-decoration:none }}
  a:hover {{ text-decoration:underline }}
  @media(max-width:700px) {{ .stats{{grid-template-columns:repeat(2,1fr)}} }}
</style>
</head>
<body>
<header>
  <div>
    <h1>📡 COEP Technetu — Monitor Dashboard</h1>
    <div class="sub">Automated website change tracker · GitHub Actions · ₹0</div>
  </div>
  <div class="updated">Updated: {updated_at}</div>
</header>

<div class="container">

  <!-- Stats -->
  <div class="stats">
    {stat_card(total_changes, "Total Changes", "#2471a3")}
    {stat_card(week_changes,  "This Week",     "#1a7a1a")}
    {stat_card(total_pdfs,    "PDFs Archived", "#6c3483")}
    {stat_card(len(upcoming_dl), "Upcoming Deadlines", "#c0392b")}
  </div>

  <!-- Upcoming Deadlines -->
  <div class="card">
    <div class="card-header">
      📅 Upcoming Deadlines
      <span style="font-size:11px;font-weight:normal;color:#888">Next 30 days</span>
    </div>
    <table>
      <tr><th>When</th><th>Date</th><th>Description</th><th>Type</th><th>Source</th></tr>
      {deadline_rows}
    </table>
  </div>

  <!-- Recent Changes -->
  <div class="card">
    <div class="card-header">
      🔔 Recent Changes
      <span style="font-size:11px;font-weight:normal;color:#888">Last 20 detections</span>
    </div>
    <table>
      <tr><th>Time</th><th>Page</th><th>Score</th><th>Sections</th>
          <th>AI Summary</th><th>PDFs</th><th>Keywords</th></tr>
      {change_rows}
    </table>
  </div>

  <!-- Top Keywords -->
  <div class="card">
    <div class="card-header">🏷️ Top Keywords Detected (all time)</div>
    <div class="kw-pills">{kw_pills or "<span style='color:#aaa;padding:4px'>No keywords detected yet.</span>"}</div>
  </div>

</div>
</body></html>"""

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"  [dashboard] Generated → {OUTPUT_FILE}")
