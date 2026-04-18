"""
sheets_manager.py — Log every change to a shared Google Sheet
Secrets needed: GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_SHEETS_ID
Setup: Share your Google Sheet with the service account email (Editor access)
"""
import os, json
from datetime import datetime

_service_cache = None

def _get_service():
    global _service_cache
    if _service_cache: return _service_cache
    sa_json   = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    sheets_id = os.environ.get("GOOGLE_SHEETS_ID", "").strip()
    if not sa_json or not sheets_id:
        return None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(
            json.loads(sa_json),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        _service_cache = (build("sheets", "v4", credentials=creds), sheets_id)
        return _service_cache
    except Exception as e:
        print(f"  [sheets] Init failed: {e}")
        return None

def _ensure_headers(service, sheet_id):
    """Create header row if sheet is empty."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id, range="A1:K1"
        ).execute()
        if not result.get("values"):
            headers = [[
                "Timestamp", "Page", "URL", "Sections Changed",
                "New PDFs", "Keywords", "AI Summary",
                "Importance Score", "Deadlines", "Translation", "Hash"
            ]]
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id, range="A1",
                valueInputOption="RAW", body={"values": headers}
            ).execute()
    except Exception:
        pass

def log_change(page_name, page_url, section_diffs, new_pdfs,
               keywords, ai_summary, importance, deadlines,
               translation, new_hash):
    result = _get_service()
    if not result: return
    service, sheet_id = result

    _ensure_headers(service, sheet_id)

    deadline_str = "; ".join(
        f"{d.get('date_str')} – {d.get('description','')[:40]}"
        for d in deadlines[:5]
    )
    row = [[
        datetime.now().strftime("%d %b %Y %H:%M"),
        page_name,
        page_url,
        ", ".join(section_diffs.keys()),
        str(len(new_pdfs)),
        ", ".join(keywords[:10]),
        (ai_summary or "")[:200],
        str(importance.get("score", "")),
        deadline_str[:200],
        ("✓" if translation else ""),
        new_hash[:12],
    ]]
    try:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id, range="A:K",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": row}
        ).execute()
        print(f"  [sheets] Row appended.")
    except Exception as e:
        print(f"  [sheets] Append failed: {e}")

def log_deadline(deadline, page_name):
    """Log a single deadline to a separate Deadlines sheet tab."""
    result = _get_service()
    if not result: return
    service, sheet_id = result

    # Ensure Deadlines sheet exists
    try:
        meta = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        sheet_names = [s["properties"]["title"] for s in meta.get("sheets", [])]
        if "Deadlines" not in sheet_names:
            service.spreadsheets().batchUpdate(
                spreadsheetId=sheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": "Deadlines"}}}]}
            ).execute()
            headers = [["Date", "Description", "Type", "Urgency", "Page", "Tracked At"]]
            service.spreadsheets().values().update(
                spreadsheetId=sheet_id, range="Deadlines!A1",
                valueInputOption="RAW", body={"values": headers}
            ).execute()
    except Exception:
        pass

    row = [[
        deadline.get("date_str", ""),
        deadline.get("description", "")[:100],
        deadline.get("type", ""),
        deadline.get("urgency", ""),
        page_name,
        datetime.now().strftime("%d %b %Y"),
    ]]
    try:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id, range="Deadlines!A:F",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": row}
        ).execute()
    except Exception as e:
        print(f"  [sheets] Deadline log failed: {e}")
