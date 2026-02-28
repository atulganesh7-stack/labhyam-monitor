# 🌴 Labhyam Scheme Monitor

Automatically checks all 18 Kerala government scheme URLs every day.
Sends you an email alert if any page changes — so you always know when
to update the Labhyam app.

---

## How It Works

1. Runs every day at 8:00 AM IST (free via GitHub Actions)
2. Fetches each government URL and compares it to yesterday's version
3. If a page has changed → sends you an email with a summary
4. You review the change and update the app if needed

---

## One-Time Setup (takes 10 minutes)

### Step 1 — Upload this folder to GitHub

1. Go to github.com → New repository → name it `labhyam-monitor`
2. Upload all files from this folder into the repository
3. Make sure the folder structure looks like this:

```
labhyam-monitor/
├── monitor.py
├── requirements.txt
├── README.md
└── .github/
    └── workflows/
        └── monitor.yml
```

---

### Step 2 — Create a Gmail App Password

You need a special password just for this app (not your Gmail login password).

1. Go to your Google Account → myaccount.google.com
2. Click **Security** → **2-Step Verification** (must be ON)
3. Scroll down → click **App Passwords**
4. Select app: **Mail** → Select device: **Other** → type "Labhyam Monitor"
5. Click **Generate** → copy the 16-character password shown

---

### Step 3 — Add Secrets to GitHub

1. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret** and add these three:

| Secret Name | Value |
|---|---|
| `ALERT_EMAIL_FROM` | The Gmail address you just created the App Password for |
| `ALERT_EMAIL_TO` | The email address where you want to receive alerts |
| `ALERT_EMAIL_PASSWORD` | The 16-character App Password from Step 2 |

---

### Step 4 — Test It

1. Go to your GitHub repository → **Actions** tab
2. Click **Labhyam Scheme Monitor** on the left
3. Click **Run workflow** → **Run workflow** (green button)
4. Watch it run — takes about 2 minutes
5. First run will say "baseline saved" for all URLs (no alerts yet)
6. From the next day onwards, any changes will trigger an email

---

## What the Email Looks Like

When a government page changes, you receive an email with:
- Which scheme page changed
- The direct URL to go and check
- A text snippet showing what the page currently says
- A checklist of what to do next

---

## What To Do When You Get an Alert

1. Open the changed URL
2. Read what is different from what the app currently shows
3. If a **benefit amount changed** → update the number in the Malayalam HTML file
4. If a **new scheme was added** → add it to the SCHEMES array
5. If a **scheme was discontinued** → remove it from the app
6. If the page just had a cosmetic redesign → no action needed

---

## Running Locally (optional)

```bash
pip install requests beautifulsoup4
python monitor.py
```

On the first run it saves baselines. On subsequent runs it detects changes.

---

## Cost

**Zero rupees.** GitHub Actions gives 2,000 free minutes per month.
This monitor uses about 2 minutes per day = 60 minutes per month.
Well within the free limit.
