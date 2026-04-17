import os
import hashlib
import smtplib
import difflib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from bs4 import BeautifulSoup

# ── Configuration ──────────────────────────────────────────────
WEBSITE_URL = "https://www.coeptech.ac.in/"
SNAPSHOT_FILE = "snapshot.txt"

# Loaded from GitHub Secrets (never hardcode these)
EMAIL_SENDER   = os.environ["EMAIL_SENDER"]    # your Gmail address
EMAIL_PASSWORD = os.environ["EMAIL_PASSWORD"]  # Gmail App Password
EMAIL_RECEIVER = os.environ["EMAIL_RECEIVER"]  # where to send alerts (can be same)

# ── Fetch & clean website text ──────────────────────────────────
def get_page_text(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CollegeMonitor/1.0)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove noise: scripts, styles, nav, footer
    for tag in soup(["script", "style", "nav", "footer", "head"]):
        tag.decompose()

    # Return cleaned visible text
    return "\n".join(
        line.strip()
        for line in soup.get_text(separator="\n").splitlines()
        if line.strip()
    )

# ── Hash helper ─────────────────────────────────────────────────
def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

# ── Load / save snapshot ─────────────────────────────────────────
def load_snapshot() -> str | None:
    if os.path.exists(SNAPSHOT_FILE):
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return None

def save_snapshot(text: str):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        f.write(text)

# ── Build diff summary (top 30 changed lines) ───────────────────
def build_diff(old: str, new: str) -> str:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    diff = list(difflib.unified_diff(old_lines, new_lines, lineterm="", n=2))
    if not diff:
        return "(No textual diff available)"
    added   = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
    parts = []
    if added:
        parts.append("🟢 ADDED / CHANGED:\n" + "\n".join(added[:15]))
    if removed:
        parts.append("🔴 REMOVED:\n" + "\n".join(removed[:15]))
    return "\n\n".join(parts) or "(Content reorganised)"

# ── Send email alert ─────────────────────────────────────────────
def send_email(diff_text: str, old_hash: str, new_hash: str):
    timestamp = datetime.now().strftime("%d %b %Y, %I:%M %p")

    subject = f"🔔 COEP Tech website changed — {timestamp}"

    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#333;max-width:640px">
      <h2 style="color:#1a5276">COEP Technetu — Website Change Alert</h2>
      <p>A change was detected on <a href="{WEBSITE_URL}">{WEBSITE_URL}</a> at <strong>{timestamp}</strong>.</p>
      <table style="border-collapse:collapse;margin-bottom:16px">
        <tr><td style="padding:4px 12px 4px 0;color:#666">Previous hash</td>
            <td style="font-family:monospace;font-size:12px">{old_hash[:16]}…</td></tr>
        <tr><td style="padding:4px 12px 4px 0;color:#666">New hash</td>
            <td style="font-family:monospace;font-size:12px">{new_hash[:16]}…</td></tr>
      </table>
      <h3 style="margin-bottom:8px">What changed</h3>
      <pre style="background:#f4f4f4;padding:14px;border-radius:6px;font-size:13px;
                  white-space:pre-wrap;border-left:4px solid #2980b9">{diff_text}</pre>
      <p style="color:#888;font-size:12px">
        <a href="{WEBSITE_URL}">Open website</a> · 
        Automated by GitHub Actions · 0 ₹ cost
      </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_SENDER
    msg["To"]      = EMAIL_RECEIVER
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

    print(f"✅ Alert email sent to {EMAIL_RECEIVER}")

# ── Main ─────────────────────────────────────────────────────────
def main():
    print(f"[{datetime.now():%H:%M:%S}] Fetching {WEBSITE_URL} …")
    current_text = get_page_text(WEBSITE_URL)
    current_hash = sha256(current_text)

    old_text = load_snapshot()

    if old_text is None:
        # First run — just save the baseline
        save_snapshot(current_text)
        print("📸 First run: baseline snapshot saved. No alert sent.")
        return

    old_hash = sha256(old_text)

    if current_hash == old_hash:
        print("✅ No change detected.")
        return

    print("🔔 Change detected! Building diff and sending alert …")
    diff = build_diff(old_text, current_text)
    send_email(diff, old_hash, current_hash)

    # Save the new snapshot AFTER sending so next run compares correctly
    save_snapshot(current_text)
    print("📸 Snapshot updated.")

if __name__ == "__main__":
    main()
