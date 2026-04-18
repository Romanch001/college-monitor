# COEP Tech Website Monitor v2
**9 automations. ₹0 cost. GitHub Actions + Gmail + Telegram + WhatsApp + Claude AI.**

---

## Features
| # | Feature | Requires |
|---|---------|---------|
| 1 | WhatsApp alerts | CallMeBot setup (free) |
| 2 | Telegram alerts | Telegram Bot (free) |
| 3 | AI summary of changes | Anthropic API key |
| 4 | PDF auto-summariser | Anthropic API key |
| 5 | Keyword alerts | Built-in (config.json) |
| 6 | Change history log | Built-in (history.json in repo) |
| 7 | Weekly digest email | Built-in (Sunday 1:30 PM IST) |
| 8 | PDF archive | Built-in (archived_pdfs/ folder) |
| 9 | Monitor multiple pages | Built-in (config.json) |

---

## File structure
```
college-monitor/
├── monitor.py                  ← main script
├── config.json                 ← edit this to customise
├── modules/
│   ├── scraper.py
│   ├── notifiers.py
│   ├── ai_helper.py
│   ├── email_builder.py
│   └── history.py
├── archived_pdfs/              ← auto-created, PDFs saved here
├── snapshot.json               ← auto-created on first run
├── history.json                ← auto-created, full change log
└── .github/workflows/
    ├── monitor.yml             ← runs hourly
    └── digest.yml              ← runs every Sunday
```

---

## Setup

### Step 1 — Upload files
Upload everything from this zip to your GitHub repo maintaining the folder structure.
The critical path is `.github/workflows/` — create it via GitHub's "Create new file" with the full path.

### Step 2 — GitHub Secrets
Go to **Settings → Secrets and variables → Actions → New repository secret**

#### Required (Email)
| Secret | Value |
|--------|-------|
| `EMAIL_SENDER` | your Gmail |
| `EMAIL_PASSWORD` | Gmail App Password |
| `EMAIL_RECEIVER` | alert destination email |

#### Optional — Telegram
1. Open Telegram → search **@BotFather** → send `/newbot`
2. Follow prompts, copy the **bot token**
3. Start a chat with your bot, then visit:
   `https://api.telegram.org/botYOUR_TOKEN/getUpdates`
4. Copy the `chat.id` value

| Secret | Value |
|--------|-------|
| `TELEGRAM_BOT_TOKEN` | token from BotFather |
| `TELEGRAM_CHAT_ID` | your chat ID from getUpdates |

#### Optional — WhatsApp (CallMeBot)
1. Add **+34 644 59 78 99** to your contacts as "CallMeBot"
2. Send this WhatsApp message to that number:
   `I allow callmebot to send me messages`
3. You'll receive your API key within 2 minutes

| Secret | Value |
|--------|-------|
| `CALLMEBOT_PHONE` | your number with country code, e.g. `919876543210` |
| `CALLMEBOT_APIKEY` | key received from CallMeBot |

#### Optional — AI Summaries (Claude)
1. Go to **console.anthropic.com** → API Keys → Create key
2. New accounts get free credits to start

| Secret | Value |
|--------|-------|
| `ANTHROPIC_API_KEY` | your Anthropic API key |

---

### Step 3 — Customise config.json
Edit `config.json` to:
- **Add/remove pages** to monitor
- **Add keywords** that trigger priority alerts
- **Set `keyword_alert_only: true`** to only get alerted for important keywords
- **Toggle AI summaries** on/off

---

### Step 4 — First run
Go to **Actions → College Website Monitor → Run workflow**
- First run saves baselines for all pages — no alerts sent
- Next run onwards: full alerts for any changes

---

## Cost breakdown
| Service | Cost |
|---------|------|
| GitHub Actions (public repo) | Free, unlimited |
| Gmail SMTP | Free |
| Telegram Bot API | Free, unlimited |
| CallMeBot WhatsApp | Free |
| Claude Haiku API (AI summaries) | ~₹0.01 per change detected |
| **Total** | **≈ ₹0** |

The Claude API calls only happen when a change is detected (not every hour), so monthly cost is effectively ₹0-2 depending on how often the site changes.
