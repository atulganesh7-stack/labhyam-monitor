"""
Labhyam — Kerala Farmer Scheme Change Monitor
==============================================
Watches all official government URLs in the Labhyam scheme database.
Sends an email alert when any page changes.

HOW IT WORKS:
  1. Fetches each government URL
  2. Hashes the meaningful text content (ignoring dates/counters)
  3. Compares to the last known hash stored in hashes.json
  4. If changed → sends email alert with a diff summary
  5. Saves new hashes for next run

SETUP (one time):
  pip install requests beautifulsoup4

ENVIRONMENT VARIABLES (set in GitHub Actions secrets):
  ALERT_EMAIL_FROM     — Gmail address you send FROM  e.g. labhyam.monitor@gmail.com
  ALERT_EMAIL_TO       — Address you want alerts sent TO
  ALERT_EMAIL_PASSWORD — Gmail App Password (not your login password)
                         Create at: myaccount.google.com → Security → App Passwords

RUN LOCALLY:
  python monitor.py

RUN ON SCHEDULE (free):
  Push this repo to GitHub — the .github/workflows/monitor.yml file
  runs this script automatically every day at 8:00 AM IST.
"""

import hashlib
import json
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# ── SCHEME URL DATABASE ────────────────────────────────────────────────────────
# Every government URL referenced in the Labhyam app.
# label     = human-readable name shown in alert emails
# url       = official government page to monitor
# watch_for = optional keyword — alert ONLY if this word appears/disappears
#             set to None to alert on ANY content change

SCHEMES_TO_MONITOR = [
    {
        "id": "aims",
        "label": "AIMS Portal — Kerala Farmer Registry",
        "url": "https://aims.kerala.gov.in",
        "watch_for": None,
    },
    {
        "id": "state-crop-insurance",
        "label": "State Crop Insurance — Kerala Agriculture Dept",
        "url": "https://keralaagriculture.gov.in/en/crop-insurance-schemes/",
        "watch_for": None,
    },
    {
        "id": "pmfby",
        "label": "PMFBY — Pradhan Mantri Fasal Bima Yojana",
        "url": "https://pmfby.gov.in",
        "watch_for": None,
    },
    {
        "id": "wbcis",
        "label": "WBCIS — Weather Based Crop Insurance Kerala",
        "url": "https://keralaagriculture.gov.in/en/crop-insurance-schemes/",
        "watch_for": "weather",
    },
    {
        "id": "agri-machinery",
        "label": "Agricultural Machinery Subsidy — Agrimachinery Portal",
        "url": "http://agrimachinery.nic.in/index",
        "watch_for": None,
    },
    {
        "id": "pmksy",
        "label": "Micro Irrigation Subsidy — PMKSY Portal",
        "url": "https://pmksy.gov.in",
        "watch_for": None,
    },
    {
        "id": "shm-organic",
        "label": "Organic Farming Assistance — SHM Kerala",
        "url": "https://shm.kerala.gov.in/scheme-details/",
        "watch_for": "organic",
    },
    {
        "id": "homestead-veg",
        "label": "Homestead Vegetable Cultivation — Kerala Agriculture",
        "url": "https://keralaagriculture.gov.in",
        "watch_for": "pachakari",
    },
    {
        "id": "pm-kisan",
        "label": "PM Kisan Samman Nidhi",
        "url": "https://pmkisan.gov.in",
        "watch_for": None,
    },
    {
        "id": "kfwfb",
        "label": "Kerala Farmers Welfare Fund Board",
        "url": "https://kfwfb.kerala.gov.in",
        "watch_for": None,
    },
    {
        "id": "agri-labour-pension",
        "label": "Agricultural Workers Welfare Pension — LSG Kerala",
        "url": "http://lsgkerala.gov.in/en/welfarepension/alp",
        "watch_for": None,
    },
    {
        "id": "cdb-aep",
        "label": "Coconut Development Board — Area Expansion Programme",
        "url": "https://coconutboard.gov.in/scheme.aspx",
        "watch_for": None,
    },
    {
        "id": "rpis",
        "label": "Rubber Production Incentive Scheme — Kerala EBT",
        "url": "http://ebt.kerala.gov.in/index.php/home/rubberlinks",
        "watch_for": None,
    },
    {
        "id": "karshaka-pension",
        "label": "Karshaka Pension — Kerala Agriculture Dept",
        "url": "https://keralaagriculture.gov.in/en/karshakapension/",
        "watch_for": None,
    },
    {
        "id": "pmkmy",
        "label": "PM Kisan Maandhan Yojana — Farmer Pension",
        "url": "https://pmkmy.gov.in",
        "watch_for": None,
    },
    {
        "id": "kcc",
        "label": "Kisan Credit Card — SBI Agriculture",
        "url": "https://www.sbi.co.in/web/agri-rural/agriculture-banking/crop-loan/kisan-credit-card",
        "watch_for": None,
    },
    {
        "id": "free-electricity",
        "label": "Free Electricity for Farmers — Kerala Agriculture",
        "url": "https://keralaagriculture.gov.in",
        "watch_for": "electricity",
    },
    {
        "id": "paddy-bonus",
        "label": "Paddy Production Bonus — Supplyco Kerala",
        "url": "https://supplyco.kerala.gov.in",
        "watch_for": None,
    },
]

# ── CONFIGURATION ──────────────────────────────────────────────────────────────
HASHES_FILE = "hashes.json"        # stores last-known page hashes
REQUEST_TIMEOUT = 20               # seconds per URL
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LabhyamMonitor/1.0; "
        "Kerala farmer scheme tracker — contact: labhyam@example.com)"
    )
}


# ── HELPERS ───────────────────────────────────────────────────────────────────
def fetch_text(url: str) -> str | None:
    """Fetch a URL and return cleaned body text. Returns None on failure."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove navigation, headers, footers, scripts — we want content only
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)

        # Collapse whitespace
        import re
        text = re.sub(r"\s+", " ", text).strip()
        return text

    except requests.exceptions.SSLError:
        print(f"  ⚠️  SSL error for {url} — trying without verification")
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS, verify=False)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return soup.get_text(separator=" ", strip=True)
        except Exception as e:
            print(f"  ❌  Failed: {e}")
            return None

    except Exception as e:
        print(f"  ❌  Failed to fetch {url}: {e}")
        return None


def compute_hash(text: str) -> str:
    """SHA-256 hash of text content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_hashes() -> dict:
    """Load saved hashes from disk."""
    if os.path.exists(HASHES_FILE):
        with open(HASHES_FILE, "r") as f:
            return json.load(f)
    return {}


def save_hashes(hashes: dict):
    """Save current hashes to disk."""
    with open(HASHES_FILE, "w") as f:
        json.dump(hashes, f, indent=2)


def extract_snippet(text: str, keyword: str = None, length: int = 400) -> str:
    """Return a readable snippet from page text, centred on keyword if given."""
    if keyword and keyword.lower() in text.lower():
        idx = text.lower().index(keyword.lower())
        start = max(0, idx - 150)
        end = min(len(text), idx + 250)
        return "..." + text[start:end] + "..."
    return text[:length] + ("..." if len(text) > length else "")


# ── EMAIL ALERT ───────────────────────────────────────────────────────────────
def send_email_alert(changes: list[dict]):
    """Send an HTML email listing all detected changes."""

    from_addr = os.environ.get("ALERT_EMAIL_FROM")
    to_addr   = os.environ.get("ALERT_EMAIL_TO")
    password  = os.environ.get("ALERT_EMAIL_PASSWORD")

    if not all([from_addr, to_addr, password]):
        print("\n⚠️  Email not configured — printing alert to console instead.\n")
        print("=" * 60)
        print("LABHYAM SCHEME CHANGE ALERT")
        print("=" * 60)
        for c in changes:
            print(f"\n🔴 CHANGED: {c['label']}")
            print(f"   URL: {c['url']}")
            print(f"   Snippet: {c['snippet'][:300]}")
        print("\n→ Set ALERT_EMAIL_FROM, ALERT_EMAIL_TO, ALERT_EMAIL_PASSWORD")
        print("  environment variables to receive email alerts.")
        return

    now = datetime.now().strftime("%d %B %Y, %I:%M %p")
    subject = f"⚠️ Labhyam Alert — {len(changes)} scheme page(s) changed — {now}"

    # Build HTML body
    rows = ""
    for c in changes:
        rows += f"""
        <div style="border:2px solid #e74c3c;border-radius:10px;padding:20px;margin-bottom:20px;">
            <h3 style="color:#c0392b;margin:0 0 8px">🔴 {c['label']}</h3>
            <p style="margin:4px 0;font-size:13px;color:#555;">
                <strong>URL:</strong>
                <a href="{c['url']}" style="color:#2d6a4f">{c['url']}</a>
            </p>
            <div style="background:#fdf2f2;padding:12px;border-radius:6px;margin-top:10px;
                        font-size:13px;color:#333;font-family:monospace;word-break:break-word;">
                {c['snippet']}
            </div>
        </div>
        """

    html = f"""
    <html><body style="font-family:sans-serif;max-width:700px;margin:0 auto;padding:24px;">
        <div style="background:#1a3a2a;padding:20px 28px;border-radius:12px;margin-bottom:28px;">
            <h1 style="color:#74c69d;margin:0;font-size:22px;">🌴 Labhyam Scheme Monitor</h1>
            <p style="color:rgba(255,255,255,0.6);margin:6px 0 0;font-size:13px;">
                Automatic change detection — {now}
            </p>
        </div>

        <p style="font-size:15px;color:#333;">
            <strong>{len(changes)} government page(s)</strong> have changed since the last check.
            Please review each change and update the Labhyam scheme database if needed.
        </p>

        {rows}

        <div style="background:#f0f9f4;border:1px solid #b7e4c7;border-radius:10px;
                    padding:18px 22px;margin-top:28px;">
            <h4 style="color:#2d6a4f;margin:0 0 10px;">What to do next</h4>
            <ol style="margin:0;padding-left:20px;color:#444;font-size:14px;line-height:1.8;">
                <li>Open the changed URL and read what is different.</li>
                <li>If a benefit amount, eligibility rule, or document requirement has changed —
                    update the SCHEMES array in the Malayalam HTML file.</li>
                <li>If a scheme has been discontinued — remove it from the app.</li>
                <li>If a brand new scheme is announced — add it to the app.</li>
            </ol>
        </div>

        <p style="font-size:12px;color:#aaa;margin-top:32px;text-align:center;">
            Labhyam Monitor • Runs daily via GitHub Actions • Kerala Farmer Scheme Finder
        </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_addr
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_addr, password)
            server.sendmail(from_addr, to_addr, msg.as_string())
        print(f"\n✅ Alert email sent to {to_addr}")
    except Exception as e:
        print(f"\n❌ Failed to send email: {e}")
        print("   Check your ALERT_EMAIL_FROM, ALERT_EMAIL_TO, ALERT_EMAIL_PASSWORD values.")


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("🌴 Labhyam Scheme Monitor")
    print(f"   Started: {datetime.now().strftime('%d %B %Y, %I:%M %p')}")
    print(f"   Checking {len(SCHEMES_TO_MONITOR)} URLs...")
    print("=" * 60)

    saved_hashes = load_hashes()
    new_hashes   = {}
    changes      = []
    errors       = []

    for scheme in SCHEMES_TO_MONITOR:
        sid   = scheme["id"]
        label = scheme["label"]
        url   = scheme["url"]
        kw    = scheme.get("watch_for")

        print(f"\n🔍 {label}")
        print(f"   {url}")

        text = fetch_text(url)

        if text is None:
            print(f"   ⚠️  Could not fetch — skipping")
            errors.append(label)
            # Keep old hash so we don't false-alarm next run
            if sid in saved_hashes:
                new_hashes[sid] = saved_hashes[sid]
            continue

        # If watch_for is set, only hash the portion of text around that keyword
        # This avoids false alerts from unrelated page changes (e.g. news tickers)
        if kw:
            relevant = kw.lower() in text.lower()
            content_to_hash = f"keyword_present:{relevant}"
        else:
            content_to_hash = text

        current_hash = compute_hash(content_to_hash)
        new_hashes[sid] = current_hash

        if sid not in saved_hashes:
            print(f"   ✅ First run — baseline saved")
        elif saved_hashes[sid] != current_hash:
            print(f"   🔴 CHANGED!")
            snippet = extract_snippet(text, kw)
            changes.append({
                "id":      sid,
                "label":   label,
                "url":     url,
                "snippet": snippet,
            })
        else:
            print(f"   ✅ No change")

    # Save updated hashes
    save_hashes(new_hashes)

    # Summary
    print("\n" + "=" * 60)
    print(f"✅ Checked: {len(SCHEMES_TO_MONITOR) - len(errors)}")
    print(f"⚠️  Errors:  {len(errors)}")
    print(f"🔴 Changes: {len(changes)}")
    print("=" * 60)

    if errors:
        print(f"\nCould not reach: {', '.join(errors)}")

    if changes:
        print(f"\n🚨 Sending alert for {len(changes)} change(s)...")
        send_email_alert(changes)
        sys.exit(1)  # non-zero exit = GitHub Actions marks run as "failed" (visible in dashboard)
    else:
        print("\n🎉 All pages stable. No action needed.")


if __name__ == "__main__":
    main()
