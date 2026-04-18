"""
email_builder.py — assembles the full HTML alert email
"""
from datetime import datetime


def esc(s: str) -> str:
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


def build_alert_html(
    page_name: str,
    page_url: str,
    old_hash: str,
    new_hash: str,
    section_diffs: dict,      # {label: {added:[...], removed:[...]}}
    new_pdfs: dict,           # {url: label}
    pdf_summaries: dict,      # {url: summary_str}
    keywords_found: list,
    ai_summary: str | None,
    timestamp: str,
) -> str:

    # ── Section blocks ───────────────────────────────────────────
    section_html = ""
    for section, diff in section_diffs.items():
        added_html = ""
        if diff["added"]:
            items = "".join(f"<li>{esc(l)}</li>" for l in diff["added"][:20])
            added_html = (
                f'<p style="color:#1a7a1a;font-weight:bold;margin:6px 0 2px">🟢 Added / New content</p>'
                f'<ul style="color:#1a7a1a;margin:0 0 8px;padding-left:20px">{items}</ul>'
            )
        removed_html = ""
        if diff["removed"]:
            items = "".join(f"<li>{esc(l)}</li>" for l in diff["removed"][:20])
            removed_html = (
                f'<p style="color:#a00;font-weight:bold;margin:6px 0 2px">🔴 Removed content</p>'
                f'<ul style="color:#a00;margin:0 0 8px;padding-left:20px">{items}</ul>'
            )
        if not added_html and not removed_html:
            added_html = "<p><em>Content reorganised (structure changed)</em></p>"

        section_html += f"""
        <div style="margin-bottom:20px;border-left:4px solid #2980b9;padding:4px 0 4px 14px;
                    background:#f8fbff;border-radius:0 6px 6px 0">
          <p style="margin:0 0 6px;font-weight:bold;color:#1a5276;font-size:14px">
            📍 {esc(section)}
          </p>
          {added_html}{removed_html}
        </div>"""

    # ── Keywords ─────────────────────────────────────────────────
    kw_html = ""
    if keywords_found:
        pills = "".join(
            f'<span style="background:#fef9e7;color:#7d6608;border:1px solid #f9e79f;'
            f'border-radius:12px;padding:2px 10px;font-size:12px;margin:2px;'
            f'display:inline-block">⚠️ {esc(k)}</span>'
            for k in keywords_found
        )
        kw_html = f"""
        <div style="margin-bottom:20px;padding:12px;background:#fef9e7;
                    border:1px solid #f9e79f;border-radius:6px">
          <b>🏷️ Keywords detected:</b><br><br>{pills}
        </div>"""

    # ── AI summary ───────────────────────────────────────────────
    ai_html = ""
    if ai_summary:
        ai_html = f"""
        <div style="margin-bottom:20px;padding:14px;background:#eafaf1;
                    border-left:4px solid #27ae60;border-radius:0 6px 6px 0">
          <p style="margin:0 0 6px;font-weight:bold;color:#1a7a1a">🤖 AI Summary</p>
          <p style="margin:0;color:#1d5e2e;font-size:14px;line-height:1.6">{esc(ai_summary)}</p>
        </div>"""

    # ── PDF block ────────────────────────────────────────────────
    pdf_html = ""
    if new_pdfs:
        pdf_rows = ""
        for url, label in new_pdfs.items():
            summary = pdf_summaries.get(url, "")
            summary_html = ""
            if summary:
                # Replace bullet lines with styled HTML
                bullets = "".join(
                    f'<li style="color:#4a235a;font-size:12px">{esc(l.lstrip("•- "))}</li>'
                    for l in summary.splitlines()
                    if l.strip()
                )
                summary_html = f'<ul style="margin:4px 0 0;padding-left:18px">{bullets}</ul>'

            pdf_rows += f"""
            <tr>
              <td style="padding:10px 12px;border-bottom:1px solid #f0e6f6;vertical-align:top">
                <a href="{esc(url)}" style="color:#6c3483;font-weight:bold;text-decoration:none">
                  📄 {esc(label)}
                </a>
                {summary_html}
              </td>
            </tr>"""

        pdf_html = f"""
        <h3 style="color:#6c3483;margin:24px 0 8px;font-size:15px">
          📎 New PDF(s) Uploaded ({len(new_pdfs)})
        </h3>
        <table style="border-collapse:collapse;width:100%;border:1px solid #e8daef;border-radius:6px;overflow:hidden">
          <tr style="background:#f5eef8">
            <th style="padding:8px 12px;text-align:left;color:#6c3483;font-size:13px">
              Document &amp; AI Summary
            </th>
          </tr>
          {pdf_rows}
        </table>
        <p style="font-size:12px;color:#888;margin-top:6px">
          PDFs ≤5 MB are attached directly. Click links for larger files.
        </p>"""

    # ── Full email ───────────────────────────────────────────────
    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:720px;
                       margin:auto;padding:0;background:#fff">

      <div style="background:#154360;color:#fff;padding:20px 26px;border-radius:8px 8px 0 0">
        <h2 style="margin:0;font-size:20px">🔔 COEP Technetu — Website Change Alert</h2>
        <p style="margin:6px 0 0;font-size:13px;opacity:0.8">
          Page: <b>{esc(page_name)}</b> · Detected at {timestamp}
        </p>
      </div>

      <div style="background:#d6eaf8;padding:10px 26px;font-size:13px;color:#555;
                  border-bottom:1px solid #aed6f1">
        <a href="{esc(page_url)}" style="color:#2471a3">{esc(page_url)}</a>
        &nbsp;·&nbsp;
        Hash: <code style="font-size:11px">{old_hash[:12]}…</code>
        → <code style="font-size:11px">{new_hash[:12]}…</code>
      </div>

      <div style="padding:24px 26px">

        {ai_html}
        {kw_html}

        <h3 style="color:#154360;border-bottom:2px solid #d6eaf8;
                   padding-bottom:8px;margin:0 0 16px;font-size:15px">
          What changed &amp; where
        </h3>

        {section_html or "<p>Change detected but specific sections could not be isolated.</p>"}
        {pdf_html}

      </div>

      <div style="background:#f2f3f4;padding:12px 26px;font-size:12px;color:#888;
                  border-radius:0 0 8px 8px;border-top:1px solid #e5e8e8">
        Automated by GitHub Actions · ₹0 cost ·
        <a href="{esc(page_url)}" style="color:#2471a3">Open page</a>
      </div>

    </body></html>"""
