"""
rss_generator.py — Generate a public RSS feed (docs/feed.xml)
Anyone can subscribe to this feed in any RSS reader (Feedly, Apple News, etc.)
The feed is auto-updated every time a change is detected.
"""
import os, json, html
from datetime import datetime

RSS_FILE     = "docs/feed.xml"
HISTORY_FILE = "history.json"
FEED_TITLE   = "COEP Technetu — Website Changes"
FEED_DESC    = "Automated alerts for changes on coeptech.ac.in"
FEED_LINK    = "https://www.coeptech.ac.in/"

def generate_feed():
    os.makedirs("docs", exist_ok=True)

    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            history = json.load(f)

    # Most recent 50 items, newest first
    items = list(reversed(history[-50:]))

    def rfc822(iso_str):
        try:
            dt = datetime.fromisoformat(iso_str)
            return dt.strftime("%a, %d %b %Y %H:%M:%S +0530")
        except Exception:
            return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530")

    def item_xml(entry):
        title    = f"COEP {entry.get('page_name','?')} changed"
        link     = entry.get("page_url", FEED_LINK)
        pub_date = rfc822(entry.get("timestamp", ""))
        sections = ", ".join(entry.get("sections_changed", []))
        keywords = ", ".join(entry.get("keywords_found", []))
        summary  = entry.get("ai_summary") or ""
        n_pdfs   = len(entry.get("new_pdfs", {}))

        desc_parts = []
        if summary:   desc_parts.append(f"Summary: {summary}")
        if sections:  desc_parts.append(f"Sections changed: {sections}")
        if keywords:  desc_parts.append(f"Keywords: {keywords}")
        if n_pdfs:    desc_parts.append(f"New PDFs: {n_pdfs}")
        description = html.escape(" | ".join(desc_parts)) if desc_parts else "Website change detected."

        guid = f"coep-monitor-{entry.get('timestamp','')}-{entry.get('page_name','')}"

        return f"""    <item>
      <title>{html.escape(title)}</title>
      <link>{html.escape(link)}</link>
      <description>{description}</description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{html.escape(guid)}</guid>
    </item>"""

    items_xml  = "\n".join(item_xml(e) for e in items)
    build_date = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{html.escape(FEED_TITLE)}</title>
    <link>{FEED_LINK}</link>
    <description>{html.escape(FEED_DESC)}</description>
    <language>en-in</language>
    <lastBuildDate>{build_date}</lastBuildDate>
    <ttl>60</ttl>
{items_xml}
  </channel>
</rss>"""

    with open(RSS_FILE, "w", encoding="utf-8") as f:
        f.write(feed)
    print(f"  [rss] Feed updated ({len(items)} items) → {RSS_FILE}")
