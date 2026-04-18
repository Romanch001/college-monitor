"""
notion_manager.py — Log college notices to a Notion database
Secrets: NOTION_API_KEY, NOTION_DATABASE_ID

Setup:
  1. Go to notion.so → Settings → Integrations → New integration
  2. Copy the "Internal Integration Token" as NOTION_API_KEY
  3. Create a database in Notion with these properties:
       Title (title), Page (text), URL (url), Sections (text),
       Keywords (multi_select), Importance (number), Summary (text),
       New PDFs (number), Date (date)
  4. Open the database page → Share → Invite your integration
  5. Copy the database ID from the URL:
       notion.so/YOUR_WORKSPACE/<DATABASE_ID>?v=...
     Add as NOTION_DATABASE_ID
"""
import os, requests
from datetime import datetime

NOTION_API = "https://api.notion.com/v1"
HEADERS_TMPL = {
    "Notion-Version": "2022-06-28",
    "Content-Type":   "application/json",
}

def _creds():
    key = os.environ.get("NOTION_API_KEY", "").strip()
    db  = os.environ.get("NOTION_DATABASE_ID", "").strip()
    return (key, db) if key and db else (None, None)

def _headers():
    key, _ = _creds()
    return {**HEADERS_TMPL, "Authorization": f"Bearer {key}"}

def log_change(page_name, page_url, section_diffs, new_pdfs,
               keywords, ai_summary, importance, deadlines):
    key, db_id = _creds()
    if not key:
        print("  [notion] secrets missing — skipped"); return

    sections_str  = ", ".join(list(section_diffs.keys())[:5])
    deadlines_str = "\n".join(
        f"• {d.get('date_str','')} — {d.get('description','')[:60]}"
        for d in deadlines[:5]
    )
    body_text = ""
    if ai_summary:        body_text += f"📋 Summary:\n{ai_summary}\n\n"
    if deadlines_str:     body_text += f"📅 Deadlines:\n{deadlines_str}\n\n"
    if new_pdfs:
        body_text += f"📎 New PDFs ({len(new_pdfs)}):\n"
        for url, label in list(new_pdfs.items())[:5]:
            body_text += f"• {label}: {url}\n"

    # Keyword multi_select (Notion requires list of {name: str})
    kw_select = [{"name": k[:100]} for k in keywords[:10]]

    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Title": {
                "title": [{"text": {"content":
                    f"COEP {page_name} – {datetime.now().strftime('%d %b %Y %H:%M')}"
                }}]
            },
            "Page":       {"rich_text": [{"text": {"content": page_name}}]},
            "URL":        {"url": page_url},
            "Sections":   {"rich_text": [{"text": {"content": sections_str[:500]}}]},
            "Keywords":   {"multi_select": kw_select},
            "Importance": {"number": importance.get("score", 0)},
            "Summary":    {"rich_text": [{"text": {"content": (ai_summary or "")[:2000]}}]},
            "New PDFs":   {"number": len(new_pdfs)},
            "Date":       {"date": {"start": datetime.now().strftime("%Y-%m-%d")}},
        },
        "children": [],
    }

    # Add body text as content blocks
    if body_text:
        for para in body_text.split("\n\n"):
            if para.strip():
                payload["children"].append({
                    "object": "block", "type": "paragraph",
                    "paragraph": {"rich_text": [{"text": {"content": para[:2000]}}]}
                })

    try:
        r = requests.post(f"{NOTION_API}/pages", headers=_headers(),
                          json=payload, timeout=20)
        if r.status_code == 200:
            print("  [notion] Page created.")
        else:
            print(f"  [notion] Failed {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  [notion] Error: {e}")
