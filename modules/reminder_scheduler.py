"""
reminder_scheduler.py — Escalating deadline reminders
Runs hourly via GitHub Actions. Checks deadlines.json and sends:
  7 days left → Email only
  3 days left → Email + Telegram
  1 day left  → Email + Telegram (urgent)
  Same day    → Email + Telegram (TODAY!)
"""
from datetime import datetime
from modules.calendar_manager import load_deadlines, save_deadlines, _try_parse_date, mark_reminded
from modules.notifiers import send_email, send_telegram

def _urgency_color(days):
    if days <= 0:  return "#c0392b"   # red — today/overdue
    if days == 1:  return "#e74c3c"   # red
    if days <= 3:  return "#e67e22"   # orange
    return "#2980b9"                   # blue

def _emoji(days):
    if days <= 0: return "🚨"
    if days == 1: return "⏰"
    if days <= 3: return "⚠️"
    return "📅"

def check_and_send_reminders():
    deadlines = load_deadlines()
    now       = datetime.now()
    sent      = 0

    for dl in deadlines:
        parsed = _try_parse_date(dl.get("date_str", ""))
        if not parsed: continue
        days_left = (parsed - now).days

        # Determine which reminder level to send
        level = None
        if   days_left <= 0  and not dl.get("reminded_1"): level = "1"   # past/today
        elif days_left == 1  and not dl.get("reminded_1"): level = "1"
        elif days_left <= 3  and not dl.get("reminded_3"): level = "3"
        elif days_left <= 7  and not dl.get("reminded_7"): level = "7"

        if not level: continue

        desc      = dl.get("description", "Deadline")
        dl_type   = dl.get("type", "other")
        page      = dl.get("page_name", "COEP")
        page_url  = dl.get("page_url", "https://www.coeptech.ac.in/")
        date_str  = dl.get("date_str", "")
        emoji     = _emoji(days_left)
        color     = _urgency_color(days_left)
        day_label = (
            "TODAY!" if days_left <= 0
            else "TOMORROW!" if days_left == 1
            else f"in {days_left} days"
        )

        # ── Email ────────────────────────────────────────────────
        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
          <div style="background:{color};color:#fff;padding:20px;border-radius:8px 8px 0 0">
            <h2 style="margin:0">{emoji} Deadline Reminder — {day_label}</h2>
          </div>
          <div style="padding:20px;border:1px solid #eee;border-radius:0 0 8px 8px">
            <table style="width:100%;border-collapse:collapse">
              <tr><td style="padding:8px;color:#666;width:120px">Deadline</td>
                  <td style="padding:8px;font-weight:bold">{desc}</td></tr>
              <tr><td style="padding:8px;color:#666">Date</td>
                  <td style="padding:8px;font-weight:bold;color:{color}">{date_str}</td></tr>
              <tr><td style="padding:8px;color:#666">Type</td>
                  <td style="padding:8px">{dl_type.title()}</td></tr>
              <tr><td style="padding:8px;color:#666">Source</td>
                  <td style="padding:8px"><a href="{page_url}">{page}</a></td></tr>
            </table>
          </div>
          <p style="color:#aaa;font-size:12px;text-align:center">
            COEP Monitor · GitHub Actions · ₹0
          </p>
        </body></html>"""

        send_email(
            subject   = f"{emoji} COEP Deadline {day_label}: {desc[:60]}",
            html_body = html_body,
        )

        # ── Telegram (3 days or less) ────────────────────────────
        if days_left <= 3:
            tg_msg = (
                f"{emoji} <b>COEP Deadline Reminder</b>\n\n"
                f"<b>{desc}</b>\n"
                f"📅 Date: <b>{date_str}</b> ({day_label})\n"
                f"📌 Type: {dl_type.title()}\n"
                f'🔗 <a href="{page_url}">{page}</a>'
            )
            send_telegram(tg_msg)

        mark_reminded(desc, date_str, level)
        sent += 1
        print(f"  [reminder] Sent {level}-day reminder for: {desc[:50]}")

    if not sent:
        print("  [reminder] No reminders to send.")

    return sent
