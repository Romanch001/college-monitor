"""
calendar_manager.py — Google Calendar (auto-create events) + local deadline tracker
Secrets needed: GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_CALENDAR_ID
Setup: see README — share your Google Calendar with the service account email
"""
import os, json
from datetime import datetime, timedelta

DEADLINES_FILE = "deadlines.json"

# ── Local deadline tracker ───────────────────────────────────────
def load_deadlines():
    if os.path.exists(DEADLINES_FILE):
        with open(DEADLINES_FILE, "r") as f:
            return json.load(f)
    return []

def save_deadlines(deadlines):
    with open(DEADLINES_FILE, "w") as f:
        json.dump(deadlines, f, indent=2)

def track_deadlines(extracted_deadlines, page_name, page_url):
    """Add newly extracted deadlines to local tracker. Deduplicate."""
    existing = load_deadlines()
    existing_keys = {(d["description"][:50], d["date_str"]) for d in existing}
    added = 0
    for dl in extracted_deadlines:
        key = (dl.get("description", "")[:50], dl.get("date_str", ""))
        if key not in existing_keys:
            existing.append({
                **dl,
                "page_name":  page_name,
                "page_url":   page_url,
                "tracked_at": datetime.now().isoformat(),
                "reminded_7":  False,
                "reminded_3":  False,
                "reminded_1":  False,
            })
            existing_keys.add(key)
            added += 1
    if added:
        save_deadlines(existing)
        print(f"  [calendar] {added} new deadline(s) tracked locally.")

def get_upcoming_deadlines(days=7):
    """Return deadlines within the next N days that haven't been reminded."""
    deadlines = load_deadlines()
    upcoming  = []
    now       = datetime.now()
    for dl in deadlines:
        parsed = _try_parse_date(dl.get("date_str", ""))
        if not parsed: continue
        diff = (parsed - now).days
        if 0 <= diff <= days:
            dl["days_left"] = diff
            upcoming.append(dl)
    return sorted(upcoming, key=lambda d: d.get("days_left", 99))

def mark_reminded(description, date_str, level):
    """level: '7', '3', or '1'"""
    deadlines = load_deadlines()
    for dl in deadlines:
        if dl.get("description", "")[:50] == description[:50] and dl.get("date_str") == date_str:
            dl[f"reminded_{level}"] = True
    save_deadlines(deadlines)

def _try_parse_date(date_str):
    formats = [
        "%d %b %Y", "%d %B %Y", "%B %d, %Y", "%d/%m/%Y",
        "%d-%m-%Y", "%Y-%m-%d", "%d %b", "%d %B",
    ]
    for fmt in formats:
        try:
            d = datetime.strptime(date_str.strip(), fmt)
            # If no year, assume current or next year
            if d.year == 1900:
                d = d.replace(year=datetime.now().year)
                if d < datetime.now():
                    d = d.replace(year=datetime.now().year + 1)
            return d
        except Exception:
            continue
    return None

# ── Google Calendar ──────────────────────────────────────────────
def _get_calendar_service():
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    cal_id  = os.environ.get("GOOGLE_CALENDAR_ID", "").strip()
    if not sa_json or not cal_id:
        return None, None
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(
            json.loads(sa_json),
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        return build("calendar", "v3", credentials=creds), cal_id
    except Exception as e:
        print(f"  [calendar] Service init failed: {e}")
        return None, None

def create_calendar_event(deadline, page_name):
    """Create a Google Calendar event for a deadline."""
    service, cal_id = _get_calendar_service()
    if not service: return

    parsed = _try_parse_date(deadline.get("date_str", ""))
    if not parsed:
        print(f"  [calendar] Could not parse date: {deadline.get('date_str')}")
        return

    desc     = deadline.get("description", "Deadline")
    dl_type  = deadline.get("type", "other")
    emoji    = {"exam":"📝","result":"📊","fee":"💰","admission":"🎓","event":"📅"}.get(dl_type, "📌")
    date_str = parsed.strftime("%Y-%m-%d")

    event = {
        "summary":     f"{emoji} COEP: {desc[:80]}",
        "description": f"Source: {page_name}\nURL: {deadline.get('page_url','')}\n\nTracked by COEP Monitor",
        "start":       {"date": date_str, "timeZone": "Asia/Kolkata"},
        "end":         {"date": (parsed + timedelta(days=1)).strftime("%Y-%m-%d"), "timeZone": "Asia/Kolkata"},
        "reminders":   {"useDefault": False, "overrides": [
            {"method": "email",  "minutes": 24 * 60},
            {"method": "popup",  "minutes": 60},
        ]},
        "colorId": "11",   # red
    }
    try:
        service.events().insert(calendarId=cal_id, body=event).execute()
        print(f"  [calendar] Event created: {desc[:50]} on {date_str}")
    except Exception as e:
        print(f"  [calendar] Event creation failed: {e}")

def add_all_deadlines_to_calendar(deadlines, page_name):
    for dl in deadlines:
        create_calendar_event(dl, page_name)
