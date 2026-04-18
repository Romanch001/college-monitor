"""
notifiers.py — send alerts via Email, Telegram, WhatsApp (CallMeBot)
Every channel is optional — if its secret is missing it is silently skipped.
"""
import os
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from urllib.parse import quote


# ── Helpers ──────────────────────────────────────────────────────
def esc(s: str) -> str:
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

def _env(key: str) -> str | None:
    v = os.environ.get(key, "").strip()
    return v if v else None


# ═══════════════════════════════════════════════════════════════════
# EMAIL
# ═══════════════════════════════════════════════════════════════════
def send_email(
    subject: str,
    html_body: str,
    attachments: list,       # [(filename, bytes), ...]
):
    sender   = _env("EMAIL_SENDER")
    password = _env("EMAIL_PASSWORD")
    receiver = _env("EMAIL_RECEIVER")
    if not all([sender, password, receiver]):
        print("  [email] Missing secrets — skipped.")
        return

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = receiver
    msg.attach(MIMEText(html_body, "html"))

    for filename, pdf_bytes in attachments:
        part = MIMEApplication(pdf_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(sender, password)
        srv.sendmail(sender, receiver, msg.as_string())
    print(f"  [email] Sent to {receiver} ({len(attachments)} attachment(s))")


# ═══════════════════════════════════════════════════════════════════
# TELEGRAM
# ═══════════════════════════════════════════════════════════════════
def send_telegram(message: str):
    """
    Secrets needed:
      TELEGRAM_BOT_TOKEN  — from @BotFather
      TELEGRAM_CHAT_ID    — your chat/group ID
    """
    token   = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("  [telegram] Missing secrets — skipped.")
        return

    # Telegram HTML mode: bold, italic, links only
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id":    chat_id,
        "text":       message[:4000],   # Telegram limit
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        print("  [telegram] Message sent.")
    except Exception as e:
        print(f"  [telegram] Failed: {e}")


def build_telegram_message(
    page_name: str,
    page_url: str,
    section_diffs: dict,
    new_pdfs: dict,
    keywords_found: list,
    ai_summary: str | None,
) -> str:
    lines = [f"🔔 <b>COEP Website Change — {page_name}</b>"]
    lines.append(f'🔗 <a href="{page_url}">{page_url}</a>\n')

    if ai_summary:
        lines.append(f"🤖 <b>AI Summary:</b>\n{ai_summary}\n")

    if keywords_found:
        kws = ", ".join(f"<code>{k}</code>" for k in keywords_found[:8])
        lines.append(f"🏷 <b>Keywords:</b> {kws}\n")

    for section, diff in list(section_diffs.items())[:3]:
        lines.append(f"📍 <b>{section}</b>")
        for line in diff["added"][:5]:
            lines.append(f"  🟢 {line[:120]}")
        for line in diff["removed"][:3]:
            lines.append(f"  🔴 {line[:120]}")
        lines.append("")

    if new_pdfs:
        lines.append(f"📎 <b>{len(new_pdfs)} new PDF(s):</b>")
        for url, label in list(new_pdfs.items())[:5]:
            lines.append(f'  • <a href="{url}">{label[:60]}</a>')

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# WHATSAPP (via CallMeBot — free, no credit card)
# ═══════════════════════════════════════════════════════════════════
def send_whatsapp(message: str):
    """
    Secrets needed:
      CALLMEBOT_PHONE   — your WhatsApp number with country code (e.g. 919876543210)
      CALLMEBOT_APIKEY  — API key from CallMeBot setup

    One-time setup:
      1. Add +34 644 59 78 99 to your WhatsApp contacts as "CallMeBot"
      2. Send: I allow callmebot to send me messages
      3. You'll receive your API key within 2 minutes
    """
    phone  = _env("CALLMEBOT_PHONE")
    apikey = _env("CALLMEBOT_APIKEY")
    if not phone or not apikey:
        print("  [whatsapp] Missing secrets — skipped.")
        return

    # Strip emojis for WhatsApp (CallMeBot may reject them)
    clean = message.encode("ascii", "ignore").decode()[:1000]
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={phone}&text={quote(clean)}&apikey={apikey}"
    )
    try:
        r = requests.get(url, timeout=15)
        if "Message Sent" in r.text or r.status_code == 200:
            print("  [whatsapp] Message sent.")
        else:
            print(f"  [whatsapp] Unexpected response: {r.text[:200]}")
    except Exception as e:
        print(f"  [whatsapp] Failed: {e}")


def build_whatsapp_message(
    page_name: str,
    page_url: str,
    section_diffs: dict,
    new_pdfs: dict,
    keywords_found: list,
    ai_summary: str | None,
) -> str:
    lines = [
        f"COEP Website Change Alert",
        f"Page: {page_name}",
        f"URL: {page_url}",
        "",
    ]
    if ai_summary:
        lines += [f"Summary: {ai_summary}", ""]
    if keywords_found:
        lines.append(f"Keywords: {', '.join(keywords_found[:6])}")
    for section, diff in list(section_diffs.items())[:2]:
        lines.append(f"\n[{section}]")
        for l in diff["added"][:4]:
            lines.append(f"+ {l[:100]}")
        for l in diff["removed"][:2]:
            lines.append(f"- {l[:100]}")
    if new_pdfs:
        lines.append(f"\n{len(new_pdfs)} new PDF(s) detected.")
        for url, label in list(new_pdfs.items())[:3]:
            lines.append(f"- {label[:60]}: {url}")
    return "\n".join(lines)
