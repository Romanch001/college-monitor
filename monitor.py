"""
monitor.py — COEP Tech Website Monitor v3
All features integrated: AI scoring, deadlines, translation, duplicate filter,
Google Calendar, Google Sheets, Notion, Discord, RSS, Dashboard, PDF intelligence.

Usage:
  python monitor.py              → check all pages
  python monitor.py --digest     → send weekly digest email
  python monitor.py --reminders  → check & send deadline reminders
  python monitor.py --dashboard  → regenerate dashboard only
"""
import os, sys, json, hashlib
from datetime import datetime
from urllib.parse import urlparse

# ── Modules ──────────────────────────────────────────────────────
from modules.scraper          import fetch_soup, extract_sections, extract_pdfs, \
                                     download_pdf, find_keywords, sha256, compute_diff
from modules.ai_helper        import summarise_diff, summarise_pdf, score_importance, \
                                     extract_deadlines, translate_text, parse_timetable
from modules.notifiers        import send_email, send_telegram, send_discord, \
                                     build_telegram_msg, build_discord_embeds
from modules.email_builder    import build_alert_html
from modules.history          import append_history, build_weekly_digest_html
from modules.pdf_intelligence import archive_pdf, is_timetable, get_previous_version, \
                                     compare_pdf_versions, load_pdf_index
from modules.calendar_manager import track_deadlines, add_all_deadlines_to_calendar
from modules.sheets_manager   import log_change as sheets_log, log_deadline as sheets_log_deadline
from modules.notion_manager   import log_change as notion_log
from modules.rss_generator    import generate_feed
from modules.dashboard_generator import generate_dashboard
from modules.reminder_scheduler  import check_and_send_reminders

# ── Config ───────────────────────────────────────────────────────
with open("config.json", encoding="utf-8") as f:
    CFG = json.load(f)

SNAPSHOT_FILE  = "snapshot.json"
MAX_PDF_BYTES  = int(CFG.get("max_pdf_size_mb", 5)) * 1024 * 1024
MAX_PDF_ATTACH = int(CFG.get("max_pdfs_per_alert", 3))
KEYWORDS       = CFG.get("keywords", [])
KEYWORD_ONLY   = CFG.get("keyword_alert_only", False)
MIN_SCORE      = int(CFG.get("min_importance_score", 4))
SECTION_SEL    = CFG.get("section_selectors", [])

SEEN_FILE = "seen_notices.json"

# ── Snapshot helpers ─────────────────────────────────────────────
def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE) as f: return json.load(f)
    return {}

def save_snapshot(data):
    with open(SNAPSHOT_FILE, "w") as f: json.dump(data, f, ensure_ascii=False, indent=2)

# ── Duplicate filter ─────────────────────────────────────────────
def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f: return set(json.load(f))
    return set()

def save_seen(seen_set):
    items = list(seen_set)[-2000:]   # keep last 2000
    with open(SEEN_FILE, "w") as f: json.dump(items, f)

def is_duplicate(diff_hash):
    return diff_hash in load_seen()

def mark_seen(diff_hash):
    seen = load_seen()
    seen.add(diff_hash)
    save_seen(seen)

# ── Check one page ───────────────────────────────────────────────
def check_page(url, name, snapshot):
    print(f"\n{'─'*60}")
    print(f"[{datetime.now():%H:%M:%S}] {name} → {url}")

    try:
        soup = fetch_soup(url)
    except Exception as e:
        print(f"  ERROR: {e}"); return None

    current_secs = extract_sections(soup, SECTION_SEL)
    current_pdfs = extract_pdfs(soup, url)
    current_hash = sha256(current_secs["__full__"])

    page_key  = hashlib.md5(url.encode()).hexdigest()[:12]
    old_entry = snapshot.get(page_key, {})
    old_hash  = old_entry.get("hash", "")

    if not old_hash:
        print(f"  First run — baseline saved.")
        return {"hash": current_hash, "sections": current_secs, "pdfs": current_pdfs}

    if current_hash == old_hash:
        print("  No change."); return None

    print("  Change detected! Analysing …")

    # ── Section diffs ────────────────────────────────────────────
    old_secs      = old_entry.get("sections", {})
    section_diffs = {}
    for label, new_text in current_secs.items():
        if label == "__full__": continue
        old_text = old_secs.get(label, "")
        if sha256(new_text) != sha256(old_text):
            section_diffs[label] = compute_diff(old_text, new_text)
    if not section_diffs:
        section_diffs["Full page"] = compute_diff(
            old_secs.get("__full__", ""), current_secs["__full__"]
        )

    # ── Duplicate filter ─────────────────────────────────────────
    diff_hash = sha256(json.dumps(section_diffs, sort_keys=True))
    if is_duplicate(diff_hash):
        print("  Duplicate — already sent this exact diff. Skipping notifications.")
        return {"hash": current_hash, "sections": current_secs, "pdfs": current_pdfs}

    # ── Keywords ─────────────────────────────────────────────────
    diff_text = " ".join(
        " ".join(d.get("added", []) + d.get("removed", []))
        for d in section_diffs.values()
    )
    keywords_found = find_keywords(diff_text, KEYWORDS)
    if keywords_found: print(f"  Keywords: {keywords_found}")

    # ── Importance score ─────────────────────────────────────────
    importance = score_importance(name, section_diffs, keywords_found)
    score      = importance.get("score", 5)
    print(f"  Importance: {score}/10 — {importance.get('reason','')}")

    # keyword_only mode check
    if KEYWORD_ONLY and not keywords_found and not any(
        url for url in current_pdfs if url not in old_entry.get("pdfs", {})
    ):
        print("  keyword_only mode — no keywords, skipping.")
        return {"hash": current_hash, "sections": current_secs, "pdfs": current_pdfs}

    # min score filter
    if score < MIN_SCORE:
        print(f"  Score {score} < min {MIN_SCORE} — skipping notifications.")
        mark_seen(diff_hash)
        return {"hash": current_hash, "sections": current_secs, "pdfs": current_pdfs}

    # ── AI summary ───────────────────────────────────────────────
    ai_summary = summarise_diff(name, section_diffs)
    if ai_summary: print(f"  AI: {ai_summary[:80]}…")

    # ── Translation ──────────────────────────────────────────────
    translation = None
    if ai_summary:
        translation = translate_text(ai_summary)
        if translation: print(f"  Translation: {translation[:60]}…")

    # ── Deadline extraction ──────────────────────────────────────
    deadlines = extract_deadlines(diff_text + " " + current_secs.get("__full__","")[:2000], name)
    if deadlines:
        print(f"  {len(deadlines)} deadline(s) extracted.")
        track_deadlines(deadlines, name, url)
        add_all_deadlines_to_calendar(deadlines, name)
        for dl in deadlines:
            sheets_log_deadline(dl, name)

    # ── New PDFs ─────────────────────────────────────────────────
    old_pdfs = old_entry.get("pdfs", {})
    new_pdfs = {u: l for u, l in current_pdfs.items() if u not in old_pdfs}
    if new_pdfs: print(f"  {len(new_pdfs)} new PDF(s).")

    date_str          = datetime.now().strftime("%Y-%m-%d")
    pdf_bytes_map     = {}   # url → (bytes, size_str)
    pdf_summaries     = {}   # url → ai summary
    pdf_timetables    = {}   # url → timetable text
    pdf_version_diffs = {}   # url → version diff text

    for pdf_url, pdf_label in new_pdfs.items():
        result = download_pdf(pdf_url, MAX_PDF_BYTES)
        if not result: continue
        pdf_bytes, size_str = result
        pdf_bytes_map[pdf_url] = (pdf_bytes, size_str)
        filename = os.path.basename(urlparse(pdf_url).path) or "document.pdf"

        # Check for previous version
        old_bytes = get_previous_version(pdf_url)
        if old_bytes:
            vdiff = compare_pdf_versions(old_bytes, pdf_bytes)
            if vdiff: pdf_version_diffs[pdf_url] = vdiff

        # Archive
        archive_pdf(pdf_bytes, pdf_url, pdf_label, date_str)

        # AI summarise
        summary = summarise_pdf(pdf_bytes, filename)
        if summary:
            pdf_summaries[pdf_url] = summary
            print(f"  PDF summary: {summary[:60]}…")

        # Timetable detection
        if is_timetable(filename, pdf_label):
            tt = parse_timetable(pdf_bytes, filename)
            if tt: pdf_timetables[pdf_url] = tt

    # ── Build email attachments ───────────────────────────────────
    attachments = []
    for pdf_url, (pdf_bytes, _) in list(pdf_bytes_map.items())[:MAX_PDF_ATTACH]:
        fname = os.path.basename(urlparse(pdf_url).path) or "document.pdf"
        attachments.append((fname, pdf_bytes))

    # ── Notify: Email ────────────────────────────────────────────
    timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")
    html_body = build_alert_html(
        page_name=name, page_url=url,
        old_hash=old_hash, new_hash=current_hash,
        section_diffs=section_diffs, new_pdfs=new_pdfs,
        pdf_summaries=pdf_summaries, keywords_found=keywords_found,
        ai_summary=ai_summary, timestamp=timestamp,
        importance=importance, deadlines=deadlines,
        translation=translation, pdf_timetables=pdf_timetables,
        pdf_version_diffs=pdf_version_diffs,
    )
    send_email(
        subject=f"{'🔴' if score>=8 else '🟡' if score>=5 else '🟢'} COEP {name} [{score}/10] — {timestamp}",
        html_body=html_body, attachments=attachments,
    )

    # ── Notify: Telegram ─────────────────────────────────────────
    tg_msg = build_telegram_msg(name, url, section_diffs, new_pdfs,
                                 keywords_found, ai_summary, importance)
    send_telegram(tg_msg)
    # Send small PDFs via Telegram too
    for pdf_url, (pdf_bytes, _) in list(pdf_bytes_map.items())[:2]:
        fname = os.path.basename(urlparse(pdf_url).path) or "document.pdf"
        caption = pdf_summaries.get(pdf_url, fname)
        from modules.notifiers import send_telegram_file
        send_telegram_file(pdf_bytes, fname, caption[:500])

    # ── Notify: Discord ──────────────────────────────────────────
    embeds = build_discord_embeds(name, url, section_diffs, new_pdfs,
                                   keywords_found, ai_summary, importance, deadlines)
    send_discord(embeds=embeds)

    # ── Log: Google Sheets ───────────────────────────────────────
    sheets_log(name, url, section_diffs, new_pdfs, keywords_found,
               ai_summary, importance, deadlines, translation, current_hash)

    # ── Log: Notion ──────────────────────────────────────────────
    notion_log(name, url, section_diffs, new_pdfs, keywords_found,
               ai_summary, importance, deadlines)

    # ── Log: History ─────────────────────────────────────────────
    append_history({
        "timestamp":        datetime.now().isoformat(),
        "page_name":        name,
        "page_url":         url,
        "sections_changed": list(section_diffs.keys()),
        "new_pdfs":         new_pdfs,
        "keywords_found":   keywords_found,
        "ai_summary":       ai_summary,
        "importance_score": score,
        "deadlines":        deadlines,
    })

    mark_seen(diff_hash)
    return {"hash": current_hash, "sections": current_secs, "pdfs": current_pdfs}


# ── Weekly digest ─────────────────────────────────────────────────
def send_weekly_digest():
    print("Sending weekly digest …")
    html = build_weekly_digest_html()
    ts   = datetime.now().strftime("%d %b %Y")
    send_email(f"📊 COEP Monitor — Weekly Digest ({ts})", html)
    send_telegram(f"📊 <b>COEP Weekly Digest</b>\nCheck your email for the full report.")
    print("Digest sent.")


# ── Main ─────────────────────────────────────────────────────────
def main():
    if "--digest"    in sys.argv: return send_weekly_digest()
    if "--reminders" in sys.argv: return check_and_send_reminders()
    if "--dashboard" in sys.argv:
        generate_dashboard(); generate_feed(); return

    snapshot = load_snapshot()
    updated  = False

    for page in CFG["pages"]:
        url, name  = page["url"], page["name"]
        page_key   = hashlib.md5(url.encode()).hexdigest()[:12]
        result     = check_page(url, name, snapshot)
        if result is not None:
            snapshot[page_key] = result
            updated = True

    if updated:
        save_snapshot(snapshot)
        generate_feed()
        generate_dashboard()
        print("\n✅ Snapshot, RSS feed, and dashboard updated.")
    else:
        print("\n✅ All pages unchanged.")

if __name__ == "__main__":
    main()
