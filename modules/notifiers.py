"""
notifiers.py — Email (Gmail), Telegram Bot, Discord Webhook
Each channel is optional — silently skipped if secrets missing.
"""
import os, smtplib, requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from urllib.parse import quote

def _e(key):
    v = os.environ.get(key, "").strip()
    return v or None

def esc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

# ═══════════════════════════ EMAIL ══════════════════════════════
def send_email(subject, html_body, attachments=[]):
    sender, pwd, recv = _e("EMAIL_SENDER"), _e("EMAIL_PASSWORD"), _e("EMAIL_RECEIVER")
    if not all([sender, pwd, recv]):
        print("  [email] secrets missing — skipped"); return
    msg = MIMEMultipart("mixed")
    msg["Subject"], msg["From"], msg["To"] = subject, sender, recv
    msg.attach(MIMEText(html_body, "html"))
    for fname, data in attachments:
        p = MIMEApplication(data, _subtype="pdf")
        p.add_header("Content-Disposition", "attachment", filename=fname)
        msg.attach(p)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, pwd); s.sendmail(sender, recv, msg.as_string())
    print(f"  [email] sent ({len(attachments)} attachments)")

# ═══════════════════════ TELEGRAM ═══════════════════════════════
def send_telegram(text, parse_mode="HTML"):
    token, chat = _e("TELEGRAM_BOT_TOKEN"), _e("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("  [telegram] secrets missing — skipped"); return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text[:4000],
                  "parse_mode": parse_mode, "disable_web_page_preview": True},
            timeout=15
        )
        r.raise_for_status()
        print("  [telegram] sent")
    except Exception as e:
        print(f"  [telegram] failed: {e}")

def send_telegram_file(file_bytes, filename, caption=""):
    """Send a file (e.g. PDF) via Telegram."""
    token, chat = _e("TELEGRAM_BOT_TOKEN"), _e("TELEGRAM_CHAT_ID")
    if not token or not chat: return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendDocument",
            data={"chat_id": chat, "caption": caption[:1000]},
            files={"document": (filename, file_bytes, "application/pdf")},
            timeout=30
        )
        print(f"  [telegram] file sent: {filename}")
    except Exception as e:
        print(f"  [telegram] file send failed: {e}")

# ═══════════════════════ DISCORD ════════════════════════════════
def send_discord(content="", embeds=None):
    """
    Secret: DISCORD_WEBHOOK_URL
    Get it: Discord server → channel settings → Integrations → Webhooks → New Webhook → Copy URL
    """
    url = _e("DISCORD_WEBHOOK_URL")
    if not url:
        print("  [discord] secret missing — skipped"); return
    payload = {}
    if content: payload["content"] = content[:2000]
    if embeds:  payload["embeds"] = embeds[:10]
    try:
        r = requests.post(url, json=payload, timeout=15)
        if r.status_code in (200, 204):
            print("  [discord] sent")
        else:
            print(f"  [discord] failed {r.status_code}: {r.text[:100]}")
    except Exception as e:
        print(f"  [discord] failed: {e}")

# ═══════════════════ MESSAGE BUILDERS ═══════════════════════════
def build_telegram_msg(page_name, page_url, section_diffs, new_pdfs,
                       keywords, ai_summary, importance):
    score = importance.get("score", 0)
    emoji = "🔴" if score >= 8 else "🟡" if score >= 5 else "🟢"
    lines = [
        f"{emoji} <b>COEP {esc(page_name)} — Change Detected</b>",
        f'🔗 <a href="{page_url}">{page_url}</a>',
        f"⭐ Importance: <b>{score}/10</b> — {esc(importance.get('reason',''))}",
        "",
    ]
    if ai_summary:
        lines += [f"🤖 <b>Summary:</b> {esc(ai_summary)}", ""]
    if keywords:
        lines.append("🏷 <b>Keywords:</b> " + ", ".join(f"<code>{k}</code>" for k in keywords[:8]))
    for sec, diff in list(section_diffs.items())[:3]:
        lines.append(f"\n📍 <b>{esc(sec)}</b>")
        for l in diff.get("added", [])[:4]:   lines.append(f"  🟢 {esc(l[:100])}")
        for l in diff.get("removed", [])[:2]: lines.append(f"  🔴 {esc(l[:100])}")
    if new_pdfs:
        lines += ["", f"📎 <b>{len(new_pdfs)} new PDF(s):</b>"]
        for url, label in list(new_pdfs.items())[:4]:
            lines.append(f'  • <a href="{url}">{esc(label[:60])}</a>')
    return "\n".join(lines)

def build_discord_embeds(page_name, page_url, section_diffs, new_pdfs,
                         keywords, ai_summary, importance, deadlines):
    score  = importance.get("score", 0)
    color  = 0xFF0000 if score >= 8 else 0xFFAA00 if score >= 5 else 0x00AA00
    fields = []
    if ai_summary:
        fields.append({"name": "🤖 AI Summary", "value": ai_summary[:500], "inline": False})
    if keywords:
        fields.append({"name": "🏷️ Keywords", "value": ", ".join(keywords[:10]), "inline": True})
    fields.append({"name": "⭐ Importance", "value": f"{score}/10 — {importance.get('reason','')}", "inline": True})
    for sec, diff in list(section_diffs.items())[:2]:
        val = ""
        for l in diff.get("added", [])[:4]:   val += f"🟢 {l[:80]}\n"
        for l in diff.get("removed", [])[:2]: val += f"🔴 {l[:80]}\n"
        if val: fields.append({"name": f"📍 {sec}", "value": val[:500], "inline": False})
    if deadlines:
        dl_str = "\n".join(f"📅 {d['date_str']} — {d['description'][:60]}" for d in deadlines[:4])
        fields.append({"name": "📅 Deadlines Detected", "value": dl_str, "inline": False})
    if new_pdfs:
        pdf_str = "\n".join(f"[{label[:50]}]({url})" for url, label in list(new_pdfs.items())[:4])
        fields.append({"name": f"📎 New PDFs ({len(new_pdfs)})", "value": pdf_str[:500], "inline": False})
    return [{
        "title": f"COEP {page_name} — Website Change",
        "url": page_url,
        "color": color,
        "fields": fields,
        "footer": {"text": "COEP Monitor • GitHub Actions • ₹0"},
    }]
