"""email_builder.py — Full rich HTML alert email"""
from datetime import datetime

def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def build_alert_html(page_name, page_url, old_hash, new_hash,
                     section_diffs, new_pdfs, pdf_summaries, keywords_found,
                     ai_summary, timestamp, importance=None, deadlines=None,
                     translation=None, pdf_timetables=None, pdf_version_diffs=None):

    importance       = importance       or {"score": 5, "reason": ""}
    deadlines        = deadlines        or []
    pdf_timetables   = pdf_timetables   or {}
    pdf_version_diffs = pdf_version_diffs or {}
    score  = importance.get("score", 5)
    color  = "#c0392b" if score>=8 else "#e67e22" if score>=5 else "#27ae60"
    emoji  = "🔴" if score>=8 else "🟡" if score>=5 else "🟢"

    # ── Importance banner ────────────────────────────────────────
    importance_html = f"""
    <div style="background:{color};color:#fff;padding:10px 20px;
                display:flex;justify-content:space-between;align-items:center">
      <span style="font-size:15px;font-weight:bold">{emoji} Importance: {score}/10</span>
      <span style="font-size:13px;opacity:0.9">{esc(importance.get('reason',''))}</span>
    </div>"""

    # ── AI summary ───────────────────────────────────────────────
    ai_html = ""
    if ai_summary:
        ai_html = f"""<div style="margin-bottom:16px;padding:14px;background:#eafaf1;
                    border-left:4px solid #27ae60;border-radius:0 6px 6px 0">
          <p style="margin:0 0 4px;font-weight:bold;color:#1a7a1a">🤖 AI Summary</p>
          <p style="margin:0;font-size:14px;line-height:1.6;color:#1d5e2e">{esc(ai_summary)}</p>
        </div>"""

    # ── Translation ──────────────────────────────────────────────
    trans_html = ""
    if translation:
        trans_html = f"""<div style="margin-bottom:16px;padding:12px;background:#fef9e7;
                    border-left:4px solid #f39c12;border-radius:0 6px 6px 0">
          <p style="margin:0 0 4px;font-weight:bold;color:#7d6608">🌐 Translation (Marathi/Hindi → English)</p>
          <p style="margin:0;font-size:14px;color:#7d6608">{esc(translation)}</p>
        </div>"""

    # ── Keywords ─────────────────────────────────────────────────
    kw_html = ""
    if keywords_found:
        pills = "".join(
            f'<span style="background:#fef9e7;color:#7d6608;border:1px solid #f9e79f;'
            f'border-radius:12px;padding:2px 10px;font-size:12px;margin:2px;display:inline-block">'
            f'⚠️ {esc(k)}</span>' for k in keywords_found
        )
        kw_html = f"""<div style="margin-bottom:16px;padding:12px;background:#fef9e7;
                    border:1px solid #f9e79f;border-radius:6px">
          <b>🏷️ Keywords detected:</b><br><br>{pills}</div>"""

    # ── Deadlines ────────────────────────────────────────────────
    dl_html = ""
    if deadlines:
        rows = ""
        for dl in deadlines:
            urgency_color = "#c0392b" if dl.get("urgency")=="high" else \
                            "#e67e22" if dl.get("urgency")=="medium" else "#2980b9"
            rows += f"""<tr>
              <td style="padding:7px 10px;border-bottom:1px solid #eee;font-weight:bold;color:{urgency_color}">{esc(dl.get('date_str',''))}</td>
              <td style="padding:7px 10px;border-bottom:1px solid #eee">{esc(dl.get('description','')[:80])}</td>
              <td style="padding:7px 10px;border-bottom:1px solid #eee;color:#666">{esc(dl.get('type',''))}</td>
            </tr>"""
        dl_html = f"""<div style="margin-bottom:16px">
          <h3 style="color:#154360;font-size:14px;margin:0 0 8px">📅 Deadlines Extracted</h3>
          <table style="border-collapse:collapse;width:100%;font-size:13px;border:1px solid #d6eaf8;border-radius:6px">
            <tr style="background:#d6eaf8">
              <th style="padding:7px 10px;text-align:left;color:#154360">Date</th>
              <th style="padding:7px 10px;text-align:left;color:#154360">Description</th>
              <th style="padding:7px 10px;text-align:left;color:#154360">Type</th>
            </tr>{rows}
          </table>
          <p style="font-size:11px;color:#888;margin-top:4px">✅ Added to Google Calendar & tracked for reminders</p>
        </div>"""

    # ── Section diffs ────────────────────────────────────────────
    section_html = ""
    for section, diff in section_diffs.items():
        added_h = removed_h = ""
        if diff.get("added"):
            items = "".join(f"<li>{esc(l)}</li>" for l in diff["added"][:20])
            added_h = f'<p style="color:#1a7a1a;font-weight:bold;margin:6px 0 2px">🟢 Added</p><ul style="color:#1a7a1a;margin:0 0 6px;padding-left:18px">{items}</ul>'
        if diff.get("removed"):
            items = "".join(f"<li>{esc(l)}</li>" for l in diff["removed"][:20])
            removed_h = f'<p style="color:#a00;font-weight:bold;margin:6px 0 2px">🔴 Removed</p><ul style="color:#a00;margin:0 0 6px;padding-left:18px">{items}</ul>'
        section_html += f"""<div style="margin-bottom:16px;border-left:4px solid #2980b9;padding:4px 0 4px 14px;background:#f8fbff;border-radius:0 6px 6px 0">
          <p style="margin:0 0 4px;font-weight:bold;color:#1a5276;font-size:14px">📍 {esc(section)}</p>
          {added_h}{removed_h or (not added_h and "<p><em>Content reorganised</em></p>") or ""}
        </div>"""

    # ── PDFs ─────────────────────────────────────────────────────
    pdf_html = ""
    if new_pdfs:
        from urllib.parse import urlparse
        import os
        pdf_rows = ""
        for url, label in new_pdfs.items():
            fname    = os.path.basename(urlparse(url).path) or "document.pdf"
            summary  = pdf_summaries.get(url, "")
            timetable = pdf_timetables.get(url, "")
            vdiff    = pdf_version_diffs.get(url, "")

            extras = ""
            if summary:
                bullets = "".join(f'<li style="color:#4a235a;font-size:12px">{esc(l.lstrip("•* "))}</li>'
                                   for l in summary.splitlines() if l.strip())
                extras += f'<ul style="margin:4px 0 0;padding-left:18px">{bullets}</ul>'
            if timetable:
                extras += f'<details style="margin-top:6px"><summary style="color:#1a5276;cursor:pointer;font-size:12px">📋 View extracted timetable</summary><pre style="font-size:11px;background:#f8f8f8;padding:8px;margin-top:4px;white-space:pre-wrap">{esc(timetable[:800])}</pre></details>'
            if vdiff:
                extras += f'<details style="margin-top:4px"><summary style="color:#a00;cursor:pointer;font-size:12px">🔄 View changes from previous version</summary><pre style="font-size:11px;background:#fff8f8;padding:8px;margin-top:4px;white-space:pre-wrap">{esc(vdiff[:600])}</pre></details>'

            pdf_rows += f"""<tr><td style="padding:10px 12px;border-bottom:1px solid #f0e6f6;vertical-align:top">
              <a href="{esc(url)}" style="color:#6c3483;font-weight:bold;text-decoration:none">📄 {esc(label)}</a>
              <span style="font-size:11px;color:#888;margin-left:8px">{esc(fname)}</span>
              {extras}
            </td></tr>"""

        pdf_html = f"""<h3 style="color:#6c3483;margin:20px 0 8px;font-size:14px">📎 New PDF(s) ({len(new_pdfs)})</h3>
        <table style="border-collapse:collapse;width:100%;border:1px solid #e8daef;border-radius:6px;overflow:hidden">
          <tr style="background:#f5eef8"><th style="padding:8px 12px;text-align:left;color:#6c3483;font-size:13px">Document, Summary &amp; Details</th></tr>
          {pdf_rows}
        </table>
        <p style="font-size:11px;color:#888;margin-top:4px">PDFs ≤5 MB are attached. Click links for larger files.</p>"""

    return f"""<html><body style="font-family:Arial,sans-serif;color:#333;max-width:720px;margin:auto;padding:0;background:#fff">
      <div style="background:#154360;color:#fff;padding:20px 26px;border-radius:8px 8px 0 0">
        <h2 style="margin:0;font-size:20px">🔔 COEP Technetu — Website Change Alert</h2>
        <p style="margin:6px 0 0;font-size:13px;opacity:0.8">Page: <b>{esc(page_name)}</b> · {timestamp}</p>
      </div>
      {importance_html}
      <div style="background:#d6eaf8;padding:10px 26px;font-size:13px;color:#555;border-bottom:1px solid #aed6f1">
        <a href="{esc(page_url)}" style="color:#2471a3">{esc(page_url)}</a>
        &nbsp;·&nbsp; Hash: <code style="font-size:11px">{old_hash[:12]}…</code> → <code style="font-size:11px">{new_hash[:12]}…</code>
      </div>
      <div style="padding:24px 26px">
        {ai_html}{trans_html}{kw_html}{dl_html}
        <h3 style="color:#154360;border-bottom:2px solid #d6eaf8;padding-bottom:8px;margin:0 0 16px;font-size:15px">What changed &amp; where</h3>
        {section_html or "<p>Change detected but sections could not be isolated.</p>"}
        {pdf_html}
      </div>
      <div style="background:#f2f3f4;padding:12px 26px;font-size:12px;color:#888;border-radius:0 0 8px 8px;border-top:1px solid #e5e8e8">
        Automated by GitHub Actions · ₹0 cost · <a href="{esc(page_url)}" style="color:#2471a3">Open page</a>
      </div>
    </body></html>"""
