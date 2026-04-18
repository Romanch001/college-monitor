import os
import json
import hashlib
import smtplib
import requests
from io import BytesIO
from urllib.parse import urljoin, urlparse
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from bs4 import BeautifulSoup

# ── Configuration ───────────────────────────────────────────────
WEBSITE_URL   = "https://www.coeptech.ac.in/"
SNAPSHOT_FILE = "snapshot.json"
MAX_PDF_SIZE  = 5 * 1024 * 1024   # 5 MB — attach PDFs smaller than this
MAX_PDF_ATTACH = 3                 # attach at most 3 PDFs per alert

EMAIL_SENDER   = os.environ["EMAIL_SENDER"]
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CollegeMonitor/1.0)"}

# ── Section map: CSS selectors → human-friendly labels ──────────
SECTION_SELECTORS = [
    ("header",                        "Header / Banner"),
    (".notices, #notices",            "Notices & Announcements"),
    (".news, #news, .latest-news",    "News"),
    (".events, #events",              "Events"),
    (".admission, #admission",        "Admissions"),
    (".academics, #academics",        "Academics"),
    (".results, #results",            "Results"),
    (".tender, #tender",              "Tenders"),
    (".recruitment, #recruitment",    "Recruitment"),
    ("main, #main, .main-content",   "Main Content"),
    ("footer",                        "Footer"),
]

# ── Fetch raw soup ───────────────────────────────────────────────
def fetch_soup(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")

# ── Extract per-section text ─────────────────────────────────────
def extract_sections(soup):
    sections = {}
    used = []
    for selector, label in SECTION_SELECTORS:
        el = soup.select_one(selector)
        if el and id(el) not in used:
            used.append(id(el))
            text = "\n".join(
                line.strip()
                for line in el.get_text(separator="\n").splitlines()
                if line.strip()
            )
            if text:
                sections[label] = text

    # Full page fallback
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    full = "\n".join(
        line.strip()
        for line in soup.get_text(separator="\n").splitlines()
        if line.strip()
    )
    sections["__full__"] = full
    return sections

# ── Extract all PDF links ────────────────────────────────────────
def extract_pdfs(soup, base_url):
    pdfs = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.lower().endswith(".pdf"):
            abs_url = urljoin(base_url, href)
            label = a.get_text(strip=True) or os.path.basename(urlparse(abs_url).path)
            pdfs[abs_url] = label
    return pdfs

# ── Hash helper ──────────────────────────────────────────────────
def sha256(text):
    return hashlib.sha256(text.encode()).hexdigest()

# ── Snapshot helpers ─────────────────────────────────────────────
def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_snapshot(data):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ── HTML escape ──────────────────────────────────────────────────
def esc(s):
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# ── Diff two text blocks → HTML ──────────────────────────────────
def html_diff_block(old, new):
    old_set = set(old.splitlines())
    new_set = set(new.splitlines())
    added   = [l for l in new.splitlines() if l not in old_set][:20]
    removed = [l for l in old.splitlines() if l not in new_set][:20]
    parts = []
    if added:
        items = "".join(f"<li>{esc(l)}</li>" for l in added)
        parts.append(
            f'<p style="color:#1a7a1a;font-weight:bold;margin:4px 0">🟢 Added / New content:</p>'
            f'<ul style="color:#1a7a1a;margin:0 0 8px">{items}</ul>'
        )
    if removed:
        items = "".join(f"<li>{esc(l)}</li>" for l in removed)
        parts.append(
            f'<p style="color:#a00;font-weight:bold;margin:4px 0">🔴 Removed content:</p>'
            f'<ul style="color:#a00;margin:0 0 8px">{items}</ul>'
        )
    return "".join(parts) or "<p><em>Content was reorganised (structure changed)</em></p>"

# ── Try to download a PDF ────────────────────────────────────────
def try_download_pdf(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        r.raise_for_status()
        content = b""
        for chunk in r.iter_content(65536):
            content += chunk
            if len(content) > MAX_PDF_SIZE:
                return None  # too big
        return content, f"{len(content)/1024:.0f} KB"
    except Exception as e:
        print(f"  Warning: could not download {url}: {e}")
        return None

# ── Send email ───────────────────────────────────────────────────
def send_email(section_diffs, new_pdfs, old_hash, new_hash):
    timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
    subject   = f"COEP Tech website changed — {timestamp}"

    # Section diff blocks
    section_html = ""
    for section, diff_html in section_diffs.items():
        section_html += f"""
        <div style="margin-bottom:20px;border-left:4px solid #2980b9;padding-left:12px">
          <h3 style="margin:0 0 6px;color:#1a5276;font-size:15px">📍 {esc(section)}</h3>
          {diff_html}
        </div>"""

    # PDF blocks
    pdf_html      = ""
    attached_pdfs = []

    if new_pdfs:
        pdf_rows = ""
        attach_count = 0
        for url, label in new_pdfs.items():
            filename = os.path.basename(urlparse(url).path) or "document.pdf"
            badge = ""
            if attach_count < MAX_PDF_ATTACH:
                result = try_download_pdf(url)
                if result:
                    pdf_bytes, size_str = result
                    attached_pdfs.append((filename, pdf_bytes))
                    attach_count += 1
                    badge = f'<span style="color:#1a7a1a;font-size:11px"> ✅ Attached ({size_str})</span>'
                else:
                    badge = '<span style="color:#888;font-size:11px"> ⚠️ Too large — link only</span>'
            pdf_rows += f"""
            <tr>
              <td style="padding:7px 10px;border-bottom:1px solid #eee">
                <a href="{esc(url)}" style="color:#2471a3;text-decoration:none">{esc(label)}</a>{badge}
              </td>
              <td style="padding:7px 10px;border-bottom:1px solid #eee;font-size:12px;color:#666">{esc(filename)}</td>
            </tr>"""

        pdf_html = f"""
        <h3 style="color:#6c3483;margin:24px 0 8px">📎 New PDF(s) Uploaded</h3>
        <table style="border-collapse:collapse;width:100%;font-size:14px;border:1px solid #e8daef;border-radius:6px">
          <tr style="background:#f5eef8">
            <th style="padding:7px 10px;text-align:left;color:#6c3483">Document name</th>
            <th style="padding:7px 10px;text-align:left;color:#6c3483">Filename</th>
          </tr>
          {pdf_rows}
        </table>
        <p style="font-size:12px;color:#888">PDFs under 5 MB are attached directly. Larger ones — click the link above.</p>"""

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:700px;margin:auto;padding:0">
      <div style="background:#154360;color:#fff;padding:18px 24px;border-radius:8px 8px 0 0">
        <h2 style="margin:0;font-size:20px">🔔 COEP Technetu — Website Change Alert</h2>
        <p style="margin:6px 0 0;font-size:13px;opacity:0.8">Detected at {timestamp}</p>
      </div>
      <div style="background:#d6eaf8;padding:10px 24px;font-size:13px;color:#555;border-bottom:1px solid #aed6f1">
        <b>Page:</b> <a href="{WEBSITE_URL}" style="color:#2471a3">{WEBSITE_URL}</a>
        &nbsp;·&nbsp;
        <b>Hash:</b> <code style="font-size:11px">{old_hash[:12]}…</code>
        → <code style="font-size:11px">{new_hash[:12]}…</code>
      </div>
      <div style="padding:24px">
        <h3 style="color:#154360;border-bottom:2px solid #d6eaf8;padding-bottom:8px;margin-top:0">
          What changed &amp; where
        </h3>
        {section_html or "<p>Change detected but specific sections could not be isolated.</p>"}
        {pdf_html}
      </div>
      <div style="background:#f2f3f4;padding:12px 24px;font-size:12px;color:#888;border-radius:0 0 8px 8px;border-top:1px solid #e5e8e8">
        Automated by GitHub Actions · ₹0 cost ·
        <a href="{WEBSITE_URL}" style="color:#2471a3">Open website</a>
      </div>
    </body></html>"""

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECEIVER
    msg.attach(MIMEText(html_body, "html"))

    for filename, pdf_bytes in attached_pdfs:
        part = MIMEApplication(pdf_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

    print(f"Email sent: {len(section_diffs)} section(s) changed, "
          f"{len(new_pdfs)} new PDF(s), {len(attached_pdfs)} attached.")

# ── Main ─────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now():%H:%M:%S}] Fetching {WEBSITE_URL} …")

    soup           = fetch_soup(WEBSITE_URL)
    current_secs   = extract_sections(soup)
    current_pdfs   = extract_pdfs(soup, WEBSITE_URL)
    current_hash   = sha256(current_secs["__full__"])

    snapshot = load_snapshot()

    if snapshot is None:
        save_snapshot({"hash": current_hash, "sections": current_secs, "pdfs": current_pdfs})
        print("First run: baseline saved. No alert sent.")
        return

    old_hash = snapshot.get("hash", "")

    if current_hash == old_hash:
        print("No change detected.")
        return

    print("Change detected! Analysing sections and PDFs …")

    # Which sections changed?
    old_secs  = snapshot.get("sections", {})
    sec_diffs = {}
    for label, new_text in current_secs.items():
        if label == "__full__":
            continue
        old_text = old_secs.get(label, "")
        if sha256(new_text) != sha256(old_text):
            sec_diffs[label] = html_diff_block(old_text, new_text)

    if not sec_diffs:
        sec_diffs["Full page"] = html_diff_block(
            old_secs.get("__full__", ""), current_secs["__full__"]
        )

    # New PDFs?
    old_pdfs = snapshot.get("pdfs", {})
    new_pdfs = {url: lbl for url, lbl in current_pdfs.items() if url not in old_pdfs}
    if new_pdfs:
        print(f"  {len(new_pdfs)} new PDF(s) found.")

    send_email(sec_diffs, new_pdfs, old_hash, current_hash)

    save_snapshot({"hash": current_hash, "sections": current_secs, "pdfs": current_pdfs})
    print("Snapshot updated.")

if __name__ == "__main__":
    main()
