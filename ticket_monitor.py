#!/usr/bin/env python3
"""
🎬 Movie Ticket Availability Monitor
Uses Playwright (headless Chrome) to check BookMyShow
for IMAX 2D tickets for Project Hail Mary in Bengaluru.

Key design: BMS shows date tabs for all dates but disables ones
with no tickets. We check if the target date tab is active/enabled.
"""

import os
import re
import json
import logging
import smtplib
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CONFIG = {
    "movie_name":          "Project Hail Mary",
    "target_date":         "2026-04-02",   # Change this — YYYY-MM-DD
    "city":                "Bengaluru",
    "format_filter":       "IMAX 2D",
    "sender_email":        os.environ.get("SENDER_EMAIL", ""),
    "sender_app_password": os.environ.get("SENDER_APP_PASSWORD", ""),
    "recipient_email":     os.environ.get("RECIPIENT_EMAIL", ""),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)


def send_email(subject: str, body: str, shows: list[dict]):
    rows = "".join(
        f"<tr>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eee'>{s['theatre']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eee'>{s['time']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eee'>{s['format']}</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #eee'>"
        f"<a href='{s['url']}' style='background:#e50914;color:#fff;padding:6px 14px;"
        f"border-radius:4px;text-decoration:none;font-weight:bold'>Book Now</a></td>"
        f"</tr>"
        for s in shows
    )
    html = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:20px">
      <div style="max-width:680px;margin:auto;background:#fff;border-radius:10px;
                  overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1)">
        <div style="background:#0d0d0d;padding:24px 28px">
          <h1 style="color:#e50914;margin:0;font-size:22px">🎬 Tickets Available!</h1>
          <p style="color:#ccc;margin:6px 0 0">{CONFIG['movie_name']} · {CONFIG['format_filter']} · {CONFIG['city']}</p>
        </div>
        <div style="padding:24px 28px">
          <p style="color:#333">IMAX 2D tickets are now available for
            <strong>{CONFIG['movie_name']}</strong> on <strong>{CONFIG['target_date']}</strong>.</p>
          <table style="width:100%;border-collapse:collapse;font-size:14px">
            <thead><tr style="background:#f0f0f0">
              <th style="padding:10px 12px;text-align:left">Theatre</th>
              <th style="padding:10px 12px;text-align:left">Show Time(s)</th>
              <th style="padding:10px 12px;text-align:left">Format</th>
              <th style="padding:10px 12px;text-align:left">Link</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
          <p style="color:#888;font-size:12px;margin-top:20px">
            Checked at {datetime.now().strftime('%d %b %Y, %I:%M %p')} · via GitHub Actions
          </p>
        </div>
      </div>
    </body></html>
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = CONFIG["sender_email"]
    msg["To"]      = CONFIG["recipient_email"]
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(CONFIG["sender_email"], CONFIG["sender_app_password"])
        server.sendmail(CONFIG["sender_email"], CONFIG["recipient_email"], msg.as_string())
    log.info(f"✅ Email sent: {subject}")


def check_bookmyshow() -> list[dict]:
    target    = CONFIG["target_date"]
    date_code = target.replace("-", "")
    fmt       = CONFIG["format_filter"]
    dt        = date.fromisoformat(target)
    page_url  = (
        f"https://in.bookmyshow.com/movies/bengaluru/project-hail-mary/"
        f"buytickets/ET00481564/{date_code}/"
    )

    # Build date strings matching BMS tab format: "THU\n02\nAPR"
    day_zero   = dt.strftime("%d")          # "04"
    mon_upper  = dt.strftime("%b").upper()  # "APR"
    weekday_up = dt.strftime("%a").upper()  # "SAT"

    # The exact text of the target date tab as rendered by BMS
    target_tab_text = f"{weekday_up}\n{day_zero}\n{mon_upper}"  # e.g. "SAT\n04\nAPR"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        context.set_extra_http_headers({"Accept-Language": "en-IN,en;q=0.9"})
        page = context.new_page()

        try:
            log.info(f"BMS: loading page for {target}")
            page.goto(page_url, wait_until="networkidle", timeout=45000)
            page.wait_for_timeout(4000)
        except PWTimeout:
            log.warning("BMS: page load timed out")
        except Exception as e:
            log.warning(f"BMS: navigation error — {e}")

        # ── Find the target date tab element and inspect its state ──────
        # We use JavaScript to find the tab whose text matches our date,
        # then read ALL its attributes, classes and parent classes to
        # determine if it's active/enabled or disabled.
        result = page.evaluate(f"""
            () => {{
                const targetText = {json.dumps(target_tab_text)};

                // Find all elements whose trimmed innerText matches our date tab
                const allEls = document.querySelectorAll('*');
                let matchedEl = null;
                for (const el of allEls) {{
                    // Only look at leaf-ish nodes (not the whole body)
                    if (el.children.length <= 3 && el.innerText && el.innerText.trim() === targetText) {{
                        matchedEl = el;
                        break;
                    }}
                }}

                if (!matchedEl) {{
                    return {{ found: false, reason: 'Tab element not found for: ' + targetText }};
                }}

                // Collect info about the element and its parents (up to 4 levels)
                const info = {{
                    found: true,
                    tagName: matchedEl.tagName,
                    className: matchedEl.className,
                    disabled: matchedEl.disabled,
                    ariaDisabled: matchedEl.getAttribute('aria-disabled'),
                    ariaSelected: matchedEl.getAttribute('aria-selected'),
                    tabIndex: matchedEl.tabIndex,
                    parents: []
                }};

                let el = matchedEl.parentElement;
                for (let i = 0; i < 4 && el; i++) {{
                    info.parents.push({{
                        tag: el.tagName,
                        className: el.className,
                        disabled: el.disabled,
                        ariaDisabled: el.getAttribute('aria-disabled'),
                        ariaSelected: el.getAttribute('aria-selected'),
                        pointerEvents: window.getComputedStyle(el).pointerEvents,
                        opacity: window.getComputedStyle(el).opacity,
                        cursor: window.getComputedStyle(el).cursor,
                    }});
                    el = el.parentElement;
                }}

                // Also get computed style of the matched element itself
                const cs = window.getComputedStyle(matchedEl);
                info.pointerEvents = cs.pointerEvents;
                info.opacity       = cs.opacity;
                info.cursor        = cs.cursor;
                info.color         = cs.color;

                return info;
            }}
        """)

        log.info(f"BMS: date tab inspection result:\n{json.dumps(result, indent=2)}")

        browser.close()

    # ── Decide if tab is enabled based on what we found ────────────────
    if not result.get("found"):
        log.info(f"BMS: {result.get('reason')} — tickets not available yet")
        return []

    # Check all the signals that indicate a disabled tab
    disabled_signals = []

    if result.get("disabled"):
        disabled_signals.append("element.disabled=true")
    if result.get("ariaDisabled") == "true":
        disabled_signals.append("aria-disabled=true")
    if result.get("pointerEvents") == "none":
        disabled_signals.append("pointer-events:none")
    if result.get("opacity") and float(result.get("opacity", 1)) < 0.6:
        disabled_signals.append(f"opacity={result.get('opacity')}")
    if result.get("cursor") == "not-allowed":
        disabled_signals.append("cursor:not-allowed")

    # Check class names for disabled-like keywords
    all_classes = result.get("className", "") + " " + " ".join(
        p.get("className", "") for p in result.get("parents", [])
    )
    for kw in ["disabled", "inactive", "unavailable", "sold-out", "soldout", "grayed", "greyed"]:
        if kw in all_classes.lower():
            disabled_signals.append(f"class contains '{kw}'")

    # Check parent pointer-events / opacity
    for p in result.get("parents", [])[:2]:
        if p.get("pointerEvents") == "none":
            disabled_signals.append(f"parent pointer-events:none ({p.get('tag')})")
        if p.get("opacity") and float(p.get("opacity", 1)) < 0.6:
            disabled_signals.append(f"parent opacity={p.get('opacity')}")

    if disabled_signals:
        log.info(f"BMS: date tab is DISABLED — signals: {disabled_signals}")
        log.info("BMS: tickets not yet on sale for this date")
        return []

    log.info(f"BMS: date tab appears ENABLED — tickets are on sale! ✅")

    # Tab is enabled — now load the page again and extract show times
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-IN", timezone_id="Asia/Kolkata",
        )
        page = context.new_page()
        page.goto(page_url, wait_until="networkidle", timeout=45000)
        page.wait_for_timeout(4000)
        text = page.inner_text("body")
        browser.close()

    if "imax" not in text.lower():
        log.info("BMS: tab enabled but no IMAX shows found in page")
        return []

    times = list(dict.fromkeys(re.findall(r'\b(\d{1,2}:\d{2}\s*(?:AM|PM|am|pm))\b', text)))
    # Also extract theatre names
    theatres = re.findall(
        r'((?:PVR|INOX|Cinepolis|Miraj|Carnival)[^\n]+)\n.*?(?:IMAX)',
        text, re.I | re.S
    )

    if not times:
        log.info("BMS: IMAX found but no show times extracted")
        return []

    log.info(f"BMS: ✅ {len(times)} IMAX 2D show time(s) for {target}: {times}")

    if theatres:
        # Return one entry per theatre
        shows = []
        for i, theatre in enumerate(theatres[:6]):
            shows.append({
                "theatre": theatre.strip(),
                "time":    times[i] if i < len(times) else times[-1],
                "format":  fmt,
                "url":     page_url,
            })
        return shows
    else:
        return [{
            "theatre": "Multiple theatres — check BMS",
            "time":    ", ".join(times[:8]),
            "format":  fmt,
            "url":     page_url,
        }]


if __name__ == "__main__":
    log.info("=" * 55)
    log.info(f"🔍 {CONFIG['movie_name']} · {CONFIG['format_filter']} · {CONFIG['target_date']}")

    all_shows = check_bookmyshow()

    if not all_shows:
        log.info("❌ No IMAX 2D shows found for the requested date. Will retry.")
    else:
        log.info(f"🎟️  Found {len(all_shows)} show(s)! Sending email…")
        subject = f"🎬 {CONFIG['movie_name']} IMAX 2D tickets live on BookMyShow!"
        body = (
            f"Tickets found for {CONFIG['movie_name']} ({CONFIG['format_filter']}) "
            f"on {CONFIG['target_date']} in {CONFIG['city']}.\n\n"
            + "\n".join(f"- {s['theatre']} | {s['time']} → {s['url']}" for s in all_shows)
        )
        try:
            send_email(subject, body, all_shows)
        except Exception as e:
            log.error(f"Email failed: {e}")
            raise SystemExit(1)
