"""
monitor.py — COEP Tech website monitor v2
Checks all configured pages, diffs sections, detects PDFs,
sends rich Email + Telegram + WhatsApp alerts, logs history.

Run:  python monitor.py
      python monitor.py --digest      (send weekly digest email)
"""
import os
import sys
import json
import hashlib
from datetime import datetime
from urllib.parse import urlparse

from modules.scraper       import fetch_soup, extract_sections, extract_pdfs, \
                                  download_pdf, find_keywords, sha256, compute_diff
from modules.ai_helper     import summarise_diff, summarise_pdf
from modules.notifiers     import send_email, send_telegram, send_whatsapp, \
                                  build_telegram_message, build_whatsapp_message
from modules.email_builder import build_alert_html
from modules.history       import append_history, archive_pdf, build_weekly_digest_html


# ── Config ───────────────────────────────────────────────────────
with open("config.json", encoding="utf-8") as f:
    CFG = json.load(f)

SNAPSHOT_FILE      = "snapshot.json"
MAX_PDF_BYTES      = int(CFG.get("max_pdf_size_mb", 5)) * 1024 * 1024
MAX_PDF_ATTACH     = int(CFG.get("max_pdfs_per_alert", 3))
ARCHIVE_PDFS       = CFG.get("archive_pdfs_in_repo", True)
AI_SUMMARY         = CFG.get("ai_summary_enabled", True)
AI_PDF_SUMMARY     = CFG.get("ai_pdf_summary_enabled", True)
KEYWORDS           = CFG.get("keywords", [])
KEYWORD_ONLY       = CFG.get("keyword_alert_only", False)
SECTION_SELECTORS  = CFG.get("section_selectors", [])


# ── Snapshot helpers ─────────────────────────────────────────────
def load_snapshot() -> dict:
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_snapshot(data: dict):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── Check one page ───────────────────────────────────────────────
def check_page(url: str, name: str, snapshot: dict) -> dict | None:
    """
    Returns updated snapshot entry if changed, else None.
    Side-effects: sends notifications, archives PDFs, logs history.
    """
    print(f"\n[{datetime.now():%H:%M:%S}] Checking '{name}' → {url}")

    try:
        soup = fetch_soup(url)
    except Exception as e:
        print(f"  ERROR fetching {url}: {e}")
        return None

    current_secs = extract_sections(soup, SECTION_SELECTORS)
    current_pdfs = extract_pdfs(soup, url)
    current_hash = sha256(current_secs["__full__"])

    page_key  = hashlib.md5(url.encode()).hexdigest()[:12]
    old_entry = snapshot.get(page_key, {})
    old_hash  = old_entry.get("hash", "")

    # First run for this page
    if not old_hash:
        print(f"  First run for '{name}' — baseline saved.")
        return {
            "hash":     current_hash,
            "sections": current_secs,
            "pdfs":     current_pdfs,
        }

    if current_hash == old_hash:
        print(f"  No change.")
        return None   # signal: no update needed

    print(f"  Change detected!")

    # ── Which sections changed? ──────────────────────────────────
    old_secs     = old_entry.get("sections", {})
    section_diffs = {}
    for label, new_text in current_secs.items():
        if label == "__full__":
            continue
        old_text = old_secs.get(label, "")
        if sha256(new_text) != sha256(old_text):
            section_diffs[label] = compute_diff(old_text, new_text)

    if not section_diffs:
        section_diffs["Full page"] = compute_diff(
            old_secs.get("__full__", ""), current_secs["__full__"]
        )

    # ── New PDFs ─────────────────────────────────────────────────
    old_pdfs = old_entry.get("pdfs", {})
    new_pdfs = {u: l for u, l in current_pdfs.items() if u not in old_pdfs}
    if new_pdfs:
        print(f"  {len(new_pdfs)} new PDF(s).")

    # ── Keywords ─────────────────────────────────────────────────
    full_diff_text = " ".join(
        " ".join(d["added"] + d["removed"]) for d in section_diffs.values()
    )
    keywords_found = find_keywords(full_diff_text, KEYWORDS)
    if keywords_found:
        print(f"  Keywords: {keywords_found}")

    # Skip if keyword_only mode and no keywords matched
    if KEYWORD_ONLY and not keywords_found and not new_pdfs:
        print("  keyword_alert_only=true and no keywords matched — skipped.")
        return {
            "hash": current_hash,
            "sections": current_secs,
            "pdfs": current_pdfs,
        }

    # ── AI summary of the diff ───────────────────────────────────
    ai_summary = None
    if AI_SUMMARY:
        ai_summary = summarise_diff(name, section_diffs)
        if ai_summary:
            print(f"  AI summary: {ai_summary[:80]}…")

    # ── Download, archive, and AI-summarise new PDFs ─────────────
    pdf_bytes_map: dict[str, tuple] = {}   # url → (bytes, size_str)
    pdf_summaries: dict[str, str]   = {}   # url → ai summary

    for pdf_url, pdf_label in new_pdfs.items():
        result = download_pdf(pdf_url, MAX_PDF_BYTES)
        if result:
            pdf_bytes, size_str = result
            pdf_bytes_map[pdf_url] = (pdf_bytes, size_str)
            filename = os.path.basename(urlparse(pdf_url).path) or "document.pdf"

            # Archive
            if ARCHIVE_PDFS:
                archive_pdf(pdf_bytes, pdf_url, pdf_label)

            # AI summarise
            if AI_PDF_SUMMARY:
                summary = summarise_pdf(pdf_bytes, filename)
                if summary:
                    pdf_summaries[pdf_url] = summary
                    print(f"  PDF summary for {filename}: {summary[:60]}…")

    # ── Build attachments (up to MAX_PDF_ATTACH) ─────────────────
    attachments = []
    for pdf_url, (pdf_bytes, _) in list(pdf_bytes_map.items())[:MAX_PDF_ATTACH]:
        filename = os.path.basename(urlparse(pdf_url).path) or "document.pdf"
        attachments.append((filename, pdf_bytes))

    # ── Send notifications ───────────────────────────────────────
    timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")

    # Email
    html_body = build_alert_html(
        page_name       = name,
        page_url        = url,
        old_hash        = old_hash,
        new_hash        = current_hash,
        section_diffs   = section_diffs,
        new_pdfs        = new_pdfs,
        pdf_summaries   = pdf_summaries,
        keywords_found  = keywords_found,
        ai_summary      = ai_summary,
        timestamp       = timestamp,
    )
    send_email(
        subject     = f"🔔 COEP {name} changed — {timestamp}",
        html_body   = html_body,
        attachments = attachments,
    )

    # Telegram
    tg_msg = build_telegram_message(
        name, url, section_diffs, new_pdfs, keywords_found, ai_summary
    )
    send_telegram(tg_msg)

    # WhatsApp
    wa_msg = build_whatsapp_message(
        name, url, section_diffs, new_pdfs, keywords_found, ai_summary
    )
    send_whatsapp(wa_msg)

    # ── Log to history ───────────────────────────────────────────
    append_history({
        "timestamp":        datetime.now().isoformat(),
        "page_name":        name,
        "page_url":         url,
        "sections_changed": list(section_diffs.keys()),
        "new_pdfs":         new_pdfs,
        "keywords_found":   keywords_found,
        "ai_summary":       ai_summary,
    })

    return {
        "hash":     current_hash,
        "sections": current_secs,
        "pdfs":     current_pdfs,
    }


# ── Weekly digest ─────────────────────────────────────────────────
def send_weekly_digest():
    print("Building weekly digest …")
    html = build_weekly_digest_html()
    timestamp = datetime.now().strftime("%d %b %Y")
    send_email(
        subject     = f"📊 COEP Monitor — Weekly Digest ({timestamp})",
        html_body   = html,
        attachments = [],
    )
    # Also send short Telegram summary
    from modules.history import load_history
    from datetime import timedelta
    history  = load_history()
    cutoff   = datetime.now() - timedelta(days=7)
    recent   = [e for e in history if datetime.fromisoformat(e["timestamp"]) >= cutoff]
    tg_msg   = (
        f"📊 <b>COEP Weekly Digest</b>\n\n"
        f"Past 7 days: <b>{len(recent)}</b> change(s) across "
        f"<b>{len(set(e['page_name'] for e in recent))}</b> page(s).\n"
        f"Check your email for the full report."
    )
    send_telegram(tg_msg)
    print("Digest sent.")


# ── Main ─────────────────────────────────────────────────────────
def main():
    if "--digest" in sys.argv:
        send_weekly_digest()
        return

    snapshot = load_snapshot()
    updated  = False

    for page in CFG["pages"]:
        url  = page["url"]
        name = page["name"]
        page_key = hashlib.md5(url.encode()).hexdigest()[:12]

        result = check_page(url, name, snapshot)
        if result is not None:
            snapshot[page_key] = result
            updated = True

    if updated:
        save_snapshot(snapshot)
        print("\nSnapshot saved.")
    else:
        print("\nAll pages unchanged.")


if __name__ == "__main__":
    main()
