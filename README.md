# COEP Tech Website Monitor
Automatically checks https://www.coeptech.ac.in/ for changes and emails you.
**Cost: ₹0. Runs every hour on GitHub's free servers.**

---

## Setup (one-time, ~10 minutes)

### Step 1 — Create a GitHub repository
1. Go to https://github.com/new
2. Name it `college-monitor` (private is fine)
3. Click **Create repository**

### Step 2 — Upload these files
Upload both files maintaining this structure:
```
college-monitor/
├── monitor.py
└── .github/
    └── workflows/
        └── monitor.yml
```
You can use GitHub's web UI: click **Add file → Upload files** or use Git.

### Step 3 — Get a Gmail App Password
> You need this so the script can send email without using your real password.

1. Go to your Google Account → **Security**
2. Make sure **2-Step Verification** is ON
3. Search for **"App Passwords"** in the search bar
4. Click **App Passwords** → Select app: **Mail** → Select device: **Other** → type "CollegeMonitor"
5. Click **Generate** — copy the 16-character password shown

### Step 4 — Add GitHub Secrets
In your GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret**

Add these three secrets:

| Secret name      | Value                              |
|------------------|------------------------------------|
| `EMAIL_SENDER`   | your Gmail address (xyz@gmail.com) |
| `EMAIL_PASSWORD` | the 16-char App Password from Step 3 |
| `EMAIL_RECEIVER` | email where you want alerts (can be same) |

### Step 5 — Enable Actions
Go to the **Actions** tab in your repo and click **"I understand my workflows, go ahead and enable them"**.

### Step 6 — First run
Click **Actions → College Website Monitor → Run workflow** to trigger manually.
- First run: saves a baseline snapshot, no email sent.
- All future runs: emails you if anything changed.

---

## Customise

**Change frequency** — edit `monitor.yml` line 7:
```yaml
- cron: "0 * * * *"      # every hour (default)
- cron: "0 8,20 * * *"   # twice a day at 8am and 8pm UTC
- cron: "*/30 * * * *"   # every 30 minutes
```

**Monitor a specific page** — edit `monitor.py` line 10:
```python
WEBSITE_URL = "https://www.coeptech.ac.in/notices/"   # just notices page
```

**Monitor multiple pages** — duplicate the monitor logic in a loop:
```python
URLS = [
    "https://www.coeptech.ac.in/",
    "https://www.coeptech.ac.in/notices/",
    "https://www.coeptech.ac.in/academics/",
]
```

---

## How it works
1. GitHub's free servers wake up every hour
2. `monitor.py` fetches the website and strips all scripts/styles
3. It hashes the visible text and compares to `snapshot.txt` (stored in your repo)
4. If different → sends you an HTML email showing exactly what changed
5. Updates `snapshot.txt` and commits it back automatically

## Free tier limits
- GitHub Actions free tier: **2,000 minutes/month** for private repos
- Running every hour = 24 runs/day × ~1 min each = ~720 min/month — well within limits
- Gmail SMTP: free, unlimited for personal use

No credit card, no paid API, no server needed.
