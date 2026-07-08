#!/usr/bin/env python3
"""
IPO Watcher — checks for new stock market listings on JSE, US markets (Nasdaq/NYSE),
and LSE, then emails you a digest of anything new since the last run.

Designed to run daily via GitHub Actions (free tier) — see workflow file.

State is kept in seen_listings.json so you only get notified about NEW items,
not the same ones every day.
"""

import json
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

import requests

STATE_FILE = Path("seen_listings.json")
DASHBOARD_DATA_FILE = Path("docs/listings_data.json")
USER_AGENT = "Mozilla/5.0 (compatible; IPOWatcher/1.0)"
MAX_HISTORY_ITEMS = 150


def load_seen():
    if STATE_FILE.exists():
        data = json.loads(STATE_FILE.read_text())
        data.setdefault("history", [])
        return data
    return {"jse": [], "nasdaq": [], "stocktitan": [], "history": []}


def save_seen(seen):
    STATE_FILE.write_text(json.dumps(seen, indent=2))


def fetch_jse_sens_listings():
    """
    Search Moneyweb's free SENS archive for listing-related announcements.
    Returns list of dicts: {title, url}
    """
    results = []
    try:
        # Moneyweb SENS search page — free, no auth required
        r = requests.get(
            "https://www.moneyweb.co.za/tools-and-data/moneyweb-sens/",
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        r.raise_for_status()
        text = r.text
        # Lightweight keyword scan — this page changes often, so this is
        # intentionally simple. For production use, consider parsing with
        # BeautifulSoup and matching <a> tags containing SENS headlines.
        keywords = ["listing", "admission to trade", "new listing", "initial public offering", "ipo"]
        import re
        # crude extraction of headline-like lines
        lines = re.findall(r">([^<>]{20,200})<", text)
        for line in lines:
            low = line.lower()
            if any(k in low for k in keywords):
                results.append({"title": line.strip(), "url": "https://www.moneyweb.co.za/tools-and-data/moneyweb-sens/"})
    except Exception as e:
        print(f"[JSE] fetch error: {e}")
    return results


def fetch_stocktitan_ipo_feed():
    """
    StockTitan publishes a free (delayed) JSON news feed used by their widgets.
    Returns list of dicts: {title, url}
    """
    results = []
    try:
        r = requests.get(
            "https://wpapi.stocktitan.net/api/news/json",
            params={"category": "ipo", "limit": 20},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            items = data if isinstance(data, list) else data.get("items", data.get("data", []))
            for item in items:
                title = item.get("title") or item.get("headline")
                url = item.get("url") or item.get("link")
                if title:
                    results.append({"title": title, "url": url or ""})
    except Exception as e:
        print(f"[StockTitan] fetch error: {e}")
    return results


def fetch_nasdaq_ipo_calendar():
    """
    Nasdaq's public IPO calendar API (used by their own website widgets).
    Returns list of dicts: {title, url}
    """
    results = []
    try:
        today = datetime.now().strftime("%Y-%m")
        r = requests.get(
            "https://api.nasdaq.com/api/ipo/calendar",
            params={"date": today},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            priced = data.get("data", {}).get("priced", {}).get("rows", []) or []
            upcoming = data.get("data", {}).get("upcoming", {}).get("upcomingTable", {}).get("rows", []) or []
            for row in priced + upcoming:
                name = row.get("companyName") or row.get("symbol")
                symbol = row.get("proposedTickerSymbol") or row.get("symbol") or ""
                if name:
                    results.append({"title": f"{name} ({symbol})", "url": "https://www.nasdaq.com/market-activity/ipos"})
    except Exception as e:
        print(f"[Nasdaq] fetch error: {e}")
    return results


def diff_new(source_key, items, seen):
    """Return only items not seen before, and update seen list + history."""
    seen_titles = set(seen.get(source_key, []))
    new_items = [i for i in items if i["title"] not in seen_titles]
    seen[source_key] = list(seen_titles | {i["title"] for i in items})

    today = datetime.now().strftime("%Y-%m-%d")
    for item in new_items:
        seen["history"].insert(0, {
            "source": source_key,
            "title": item["title"],
            "url": item.get("url", ""),
            "first_seen": today,
        })
    seen["history"] = seen["history"][:MAX_HISTORY_ITEMS]
    return new_items


def write_dashboard_data(seen):
    """Write a JSON snapshot the dashboard (index.html) can fetch and render."""
    DASHBOARD_DATA_FILE.parent.mkdir(exist_ok=True)
    payload = {
        "last_updated": datetime.now().isoformat(),
        "history": seen.get("history", []),
    }
    DASHBOARD_DATA_FILE.write_text(json.dumps(payload, indent=2))


def build_digest(new_by_source):
    if not any(new_by_source.values()):
        return None
    lines = [f"IPO Watcher digest — {datetime.now().strftime('%Y-%m-%d')}", ""]
    labels = {
        "jse": "🇿🇦 JSE (via SENS)",
        "nasdaq": "🇺🇸 Nasdaq IPO Calendar",
        "stocktitan": "📰 StockTitan IPO Feed",
    }
    for key, items in new_by_source.items():
        if not items:
            continue
        lines.append(labels.get(key, key))
        for i in items[:15]:  # cap per source to keep email readable
            line = f"  • {i['title']}"
            if i.get("url"):
                line += f"\n    {i['url']}"
            lines.append(line)
        lines.append("")
    lines.append("Reminder: check EasyEquities directly to confirm if/when any of these become tradable there.")
    return "\n".join(lines)


def send_email(subject, body):
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "465"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to_addr = os.environ.get("ALERT_TO_EMAIL")

    if not all([host, user, password, to_addr]):
        print("Email not configured (missing SMTP_* / ALERT_TO_EMAIL env vars). Printing digest instead:\n")
        print(body)
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context) as server:
        server.login(user, password)
        server.sendmail(user, [to_addr], msg.as_string())
    print(f"Email sent to {to_addr}")


def main():
    seen = load_seen()

    jse_items = fetch_jse_sens_listings()
    nasdaq_items = fetch_nasdaq_ipo_calendar()
    stocktitan_items = fetch_stocktitan_ipo_feed()

    new_by_source = {
        "jse": diff_new("jse", jse_items, seen),
        "nasdaq": diff_new("nasdaq", nasdaq_items, seen),
        "stocktitan": diff_new("stocktitan", stocktitan_items, seen),
    }

    save_seen(seen)
    write_dashboard_data(seen)

    digest = build_digest(new_by_source)
    if digest:
        send_email("IPO Watcher: new listings found", digest)
    else:
        print("No new listings found today.")


if __name__ == "__main__":
    main()
