#!/usr/bin/env python3
"""
reddit_auto_pilot.py — Continuous background service that replies to Reddit posts
using alerts from ExpatScore Sniper.

Runs in an infinite loop, checks Gmail every 20 minutes, processes new alerts,
and posts comments using Playwright in headless mode with a realistic user agent
and multiple message variations.

Environment variables:
    GMAIL_USER        : email address (default: yactok25@gmail.com)
    GMAIL_APP_PASSWORD: app-specific password (required)
    REDDIT_USER       : Reddit username (required)
    REDDIT_PASS       : Reddit password (required)

Usage:
    python reddit_auto_pilot.py
"""

import os
import re
import time
import random
import imaplib
import email
import datetime
from email.header import decode_header
from playwright.sync_api import sync_playwright

# ---------- CONFIG ----------
GMAIL_USER = os.environ.get("GMAIL_USER", "yactok25@gmail.com")
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD")
if not GMAIL_PASS:
    raise ValueError("Missing GMAIL_APP_PASSWORD environment variable")

REDDIT_USER = os.environ.get("REDDIT_USER")
REDDIT_PASS = os.environ.get("REDDIT_PASS")
if not REDDIT_USER or not REDDIT_PASS:
    raise ValueError("Missing REDDIT_USER or REDDIT_PASS environment variables")

IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
CHECK_INTERVAL_SECONDS = 20 * 60  # 20 minutes

# Random delays
TYPING_DELAY_MS = random.uniform(80, 150) / 1000.0  # seconds between characters
WAIT_BEFORE_TYPING_SEC = random.uniform(60, 120)     # wait after page load

# Realistic user agent for macOS
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

# Multiple message variations (will be chosen randomly)
MARKETING_VARIATIONS = [
    """I went through the exact same struggle in Germany. After months of frustration, I put together a free guide with all the steps that finally worked for me. You can find it here: https://expatscore.de/blog/ Hope it helps!""",
    """Hey, I feel your pain – been there myself. I started documenting everything I learned about SCHUFA, banking, and taxes on a little project called ExpatScore.de. The blog has some detailed breakdowns that might save you hours of research: https://expatscore.de/blog/""",
    """Literally was in your shoes last year. It's a total mess. I wrote down everything I wish I'd known from the start – it's all free at ExpatScore.de. Check out the blog: https://expatscore.de/blog/""",
    """I've been tracking these issues for expats in Germany for a while. There's a great resource at ExpatScore.de that breaks down the whole process step by step. Definitely worth a look: https://expatscore.de/blog/"""
]


# ---------- GMAIL FUNCTIONS ----------
def fetch_unread_alerts():
    """Connect to Gmail, fetch unread messages with subject containing 'ExpatScore Sniper Alert'.
    Returns a list of tuples (uid, body_text) for each new alert.
    """
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(GMAIL_USER, GMAIL_PASS)
    mail.select("INBOX")

    # Search for unread messages with subject containing the alert text (no emoji)
    # Use CHARSET UTF-8 to avoid encoding issues.
    result, data = mail.search(None, 'CHARSET UTF-8', '(UNSEEN SUBJECT "ExpatScore Sniper Alert")')
    if result != "OK":
        mail.close()
        mail.logout()
        return []

    uids = data[0].split()
    if not uids:
        mail.close()
        mail.logout()
        return []

    alerts = []
    for uid in uids:
        result, msg_data = mail.fetch(uid, "(RFC822)")
        if result != "OK":
            continue

        raw_email = msg_data[0][1]
        email_msg = email.message_from_bytes(raw_email)

        # Extract body text
        body = None
        if email_msg.is_multipart():
            for part in email_msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    body = payload.decode("utf-8", errors="ignore")
                    break
        else:
            payload = email_msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="ignore")

        if body:
            alerts.append((uid, body))

    mail.close()
    mail.logout()
    return alerts


def parse_alert_body(body):
    """Extract Reddit URL and the marketing text from the email body."""
    url_match = re.search(r"Reddit Link:\s*(https?://[^\s]+)", body)
    if not url_match:
        return None, None
    reddit_url = url_match.group(1)

    # The marketing snippet is after "--- Ready-to-Post Marketing Snippet ---"
    snippet_start = "--- Ready-to-Post Marketing Snippet ---"
    if snippet_start in body:
        marketing_text = body.split(snippet_start, 1)[1].strip()
    else:
        parts = body.split("---")
        if len(parts) >= 2:
            marketing_text = parts[-1].strip()
        else:
            marketing_text = body.strip()

    # Remove any trailing separator lines
    marketing_text = marketing_text.split("---")[0].strip()
    return reddit_url, marketing_text


# ---------- REDDIT COMMENT FUNCTION (headless mode) ----------
def post_reddit_comment(url):
    """Use Playwright (headless) to log into Reddit and post a randomly chosen message."""
    with sync_playwright() as p:
        # Launch browser in headless mode with a realistic user agent
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        try:
            # Go directly to login page
            print("Navigating to Reddit login page...")
            page.goto("https://www.reddit.com/login/")
            page.wait_for_load_state("networkidle")

            # Small delay to let cookie banners appear
            time.sleep(2)

            # Handle cookie banner if present
            try:
                accept_btn = page.locator('button:has-text("Accept all")')
                if accept_btn.is_visible(timeout=3000):
                    accept_btn.click()
                    print("Accepted cookie banner.")
            except:
                pass

            # Wait for username field
            try:
                page.wait_for_selector('input[name="username"]', state="visible", timeout=15000)
            except Exception as e:
                print(f"Timeout waiting for username field: {e}")
                page.screenshot(path="error_debug.png")
                raise

            # Fill login form
            page.fill('input[name="username"]', REDDIT_USER)
            page.fill('input[name="password"]', REDDIT_PASS)
            page.click('button[type="submit"]')
            print("Login submitted, waiting for navigation...")
            page.wait_for_load_state("networkidle")

            # Check for CAPTCHA
            if page.locator('iframe[title*="captcha"]').count() > 0:
                print("CAPTCHA detected! Manual intervention required.")
                page.screenshot(path="captcha_detected.png")
                raise Exception("CAPTCHA page encountered, cannot proceed.")

            # Accept any post-login cookie prompts
            try:
                accept_btn = page.locator('button:has-text("Accept all")')
                if accept_btn.is_visible(timeout=3000):
                    accept_btn.click()
            except:
                pass

            # Go to the target post URL
            print(f"Navigating to post: {url}")
            page.goto(url)
            page.wait_for_load_state("networkidle")

            # Wait random delay before typing
            print(f"Waiting {WAIT_BEFORE_TYPING_SEC:.0f} seconds before typing...")
            time.sleep(WAIT_BEFORE_TYPING_SEC)

            # Find comment textarea
            comment_box = None
            try:
                comment_box = page.locator('textarea[placeholder*="What are your thoughts?"]').first
                if not comment_box.is_visible():
                    raise Exception("Not found")
            except:
                try:
                    comment_box = page.locator('textarea[name="text"]').first
                    if not comment_box.is_visible():
                        raise Exception("Not found")
                except:
                    comment_box = page.locator('textarea').first

            if not comment_box or not comment_box.is_visible():
                raise Exception("Could not find comment textarea")

            comment_box.click()
            time.sleep(random.uniform(0.5, 1.5))

            # Choose a random marketing message
            comment_text = random.choice(MARKETING_VARIATIONS)
            print("Typing comment...")
            for char in comment_text:
                page.keyboard.type(char, delay=TYPING_DELAY_MS * 1000)
                if random.random() < 0.05:
                    time.sleep(random.uniform(0.3, 1.0))

            # Click comment button
            try:
                comment_btn = page.locator('button:has-text("Comment")').first
                comment_btn.click()
            except:
                try:
                    comment_btn = page.locator('button:has-text("reply")').first
                    comment_btn.click()
                except:
                    comment_btn = page.locator('button:has-text("save")').first
                    comment_btn.click()

            print("Comment posted. Waiting for confirmation...")
            time.sleep(5)

        except Exception as e:
            print(f"Error during Reddit interaction: {e}")
            page.screenshot(path="error_debug.png")
            raise
        finally:
            browser.close()


# ---------- MARK EMAIL AS READ ----------
def mark_email_read(uid):
    """Mark a specific email as read via IMAP."""
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(GMAIL_USER, GMAIL_PASS)
    mail.select("INBOX")
    mail.store(str(uid), "+FLAGS", "\\Seen")
    mail.close()
    mail.logout()


# ---------- MAIN LOOP (continuous) ----------
def main():
    print(f"Starting Reddit Auto-Pilot service. Checking every {CHECK_INTERVAL_SECONDS // 60} minutes.")
    while True:
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M")
            print(f"[{timestamp}] Checking for new alerts...")

            alerts = fetch_unread_alerts()
            if not alerts:
                print(f"[{timestamp}] No new alerts. Waiting {CHECK_INTERVAL_SECONDS // 60} min...")
                time.sleep(CHECK_INTERVAL_SECONDS)
                continue

            for uid, body in alerts:
                reddit_url, _ = parse_alert_body(body)  # we ignore the original snippet, use our own
                if not reddit_url:
                    print(f"[{timestamp}] Skipping email {uid}: missing URL")
                    continue

                print(f"[{timestamp}] Processing: {reddit_url}")

                try:
                    post_reddit_comment(reddit_url)
                except Exception as e:
                    print(f"[{timestamp}] Failed to post comment: {e}")
                    # Do not mark email as read; will retry in next cycle
                    continue

                mark_email_read(uid)
                print(f"[{timestamp}] Comment posted and email marked read.")
                # Add a small delay between processing multiple alerts
                time.sleep(30)

        except Exception as e:
            print(f"[{timestamp}] ERROR: {e}")
            print(f"[{timestamp}] Waiting {CHECK_INTERVAL_SECONDS // 60} minutes before retry...")

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()