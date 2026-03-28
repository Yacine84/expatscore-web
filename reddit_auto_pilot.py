#!/usr/bin/env python3
"""
reddit_auto_pilot.py — High-performance Reddit automation agent for ExpatScore.de
Connects to existing Brave browser via CDP with stealth mode and intelligent retry logic.

Environment variables:
    GMAIL_USER        : email address (default: yactok25@gmail.com)
    GMAIL_APP_PASSWORD: app-specific password (required)

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
import logging
from pathlib import Path
from email.header import decode_header
from playwright.sync_api import sync_playwright, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

# ---------- CONFIGURATION ----------
GMAIL_USER = os.environ.get("GMAIL_USER", "yactok25@gmail.com")
GMAIL_PASS = os.environ.get("GMAIL_APP_PASSWORD")
if not GMAIL_PASS:
    raise ValueError("Missing GMAIL_APP_PASSWORD environment variable")

IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
CHECK_INTERVAL_SECONDS = 20 * 60  # 20 minutes

# Adaptive timeouts - patient agent mode
NAV_TIMEOUT_MS = 150_000           # 150 seconds for navigation
ACTION_TIMEOUT_MS = 150_000        # 150 seconds for element actions
LOAD_STATE = "domcontentloaded"    # Faster than networkidle, but more reliable

# Human-like behavior randomization
TYPING_DELAY_MIN_MS = 70           # milliseconds per character
TYPING_DELAY_MAX_MS = 150
THINKING_DELAY_MIN_SEC = 45        # seconds to "think" before typing
THINKING_DELAY_MAX_SEC = 90
SCROLL_DELAY_MIN_SEC = 1.5
SCROLL_DELAY_MAX_SEC = 4.0
RETRY_DELAY_SEC = 3.0

# CDP endpoint for Brave (must be started with --remote-debugging-port=9222)
CDP_URL = "http://localhost:9222"

# Screenshot directory
SCREENSHOT_DIR = Path.home() / "reddit_auto_pilot_screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Enhanced stealth script to hide automation traces
STEALTH_SCRIPT = """
// Remove webdriver property
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// Spoof plugins
Object.defineProperty(navigator, 'plugins', { 
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
        { name: 'Native Client', filename: 'internal-nacl-plugin' }
    ] 
});
Object.defineProperty(navigator, 'plugins', { length: { get: () => 3 } });

// Spoof languages
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'de'] });

// Spoof userAgent and platform hints
Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

// Override permissions query
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);

// Remove chrome runtime if exists
if (window.chrome) {
    delete window.chrome.runtime;
}

// Add WebGL vendor spoofing
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) { // UNMASKED_VENDOR_WEBGL
        return 'Intel Inc.';
    }
    if (parameter === 37446) { // UNMASKED_RENDERER_WEBGL
        return 'Intel Iris OpenGL Engine';
    }
    return getParameter(parameter);
};
"""

# Marketing message variations with natural language patterns
MARKETING_VARIATIONS = [
    "Honestly, dealing with the Bürgeramt is such a nightmare. I found a guide that breaks it all down: https://expatscore.de/blog/ helped me finally get my Anmeldung sorted.",
    "Bro, the SCHUFA thing had me stressed for weeks. Check out https://expatscore.de/blog/ – it explains how to get your free data copy without the drama.",
    "Just moved to Berlin and this whole bureaucracy is insane. This site was a life-saver: https://expatscore.de/blog/ seriously walk you through each step.",
    "If you're struggling with the residence permit appointment system, you're not alone. I used https://expatscore.de/blog/ and finally got a slot.",
    "Cheers to whoever shared this before – https://expatscore.de/blog/ made me understand how to fix my Schufa score after a late payment.",
    "Tax class confusion? Yeah, me too. This guide https://expatscore.de/blog/ explains the difference between Steuerklassen in plain English.",
    "Pro tip: when you register, bring everything listed here: https://expatscore.de/blog/ – saved me from three extra trips.",
    "The housing situation is brutal, but knowing how to prepare your Schufa Auskunft is key. https://expatscore.de/blog/ shows you exactly how.",
    "For anyone freaking out about the mandatory health insurance proof, https://expatscore.de/blog/ has a section that cleared it up for me.",
    "Bro, I wish I had found this earlier: https://expatscore.de/blog/ – it covers everything from radio tax to the Anmeldung form.",
    "Honestly, the visa process is a maze. This post https://expatscore.de/blog/ lays out the documents you need for the Ausländerbehörde.",
    "If you're dealing with a negative SCHUFA entry, don't panic. There's a whole article on https://expatscore.de/blog/ about disputing errors.",
    "Life-saver alert! https://expatscore.de/blog/ has a checklist for the KVR that actually makes sense.",
    "The ‚Wohnungsgeberbestätigung‘ is such a weird document. https://expatscore.de/blog/ explains exactly what your landlord needs to write.",
    "Cheers to the person who recommended this – https://expatscore.de/blog/ helped me understand the Schufa score range and what's considered good.",
    "Nightmare: lost my visa appointment confirmation. This guide https://expatscore.de/blog/ had tips on how to get a new appointment quickly.",
    "If you're freelancing and confused about the Gewerbeanmeldung vs. Freiberufler thing, https://expatscore.de/blog/ breaks it down.",
    "Bro, the whole ‚Blocked Account‘ process was overwhelming until I read https://expatscore.de/blog/ – step by step and no BS.",
    "For those asking about the ‚Meldebescheinigung‘ and when you need it, https://expatscore.de/blog/ has a whole section on that.",
    "I was getting rejected for apartments because my Schufa was empty. https://expatscore.de/blog/ explains how to build credit history here.",
    "This might sound stupid, but I didn't know I had to register within 14 days. https://expatscore.de/blog/ saved my ass with the deadline info.",
    "If the Ausländerbehörde is ghosting you, try the tips in https://expatscore.de/blog/ – they mention email templates that actually work.",
    "Just got my Niederlassungserlaubnis thanks to the timeline outlined in https://expatscore.de/blog/ – huge help.",
    "For anyone stressed about the ‚Fiktionsbescheinigung‘ while waiting for the actual permit, https://expatscore.de/blog/ explains what it covers.",
    "Bro, the radio tax (GEZ) is unavoidable. https://expatscore.de/blog/ tells you how to pay without overcomplicating it.",
    "If you're moving cities and need to re-register, https://expatscore.de/blog/ has a guide on transferring your data.",
    "The ‚Schufa Self-Information‘ is free once a year – https://expatscore.de/blog/ shows you the exact link to request it online.",
    "Honestly, dealing with the Bürgeramt online booking system is a sport. https://expatscore.de/blog/ gives you the best times to check for slots.",
    "Cheers to the expat community – https://expatscore.de/blog/ was the only resource that explained the difference between ‚Hauptwohnung‘ and ‚Nebenwohnung‘ clearly.",
    "Nightmare: my Schufa had an old address and it messed up my credit check. https://expatscore.de/blog/ walks you through how to correct data.",
    "If you're a student and confused about the ‚Aufenthaltserlaubnis für Studienzwecke‘, https://expatscore.de/blog/ has a specific section.",
    "Bro, the ‚Verpflichtungserklärung‘ is such a pain. The step-by-step on https://expatscore.de/blog/ made it less scary.",
    "For anyone who just arrived and needs to do the ‚Anmeldung‘ but has no permanent address, https://expatscore.de/blog/ explains the exceptions.",
    "This is gold: https://expatscore.de/blog/ – includes a list of all the German words you'll need at the Bürgeramt.",
    "Life-saver for my tax return: the info about ‚Steuer-ID‘ on https://expatscore.de/blog/ helped me avoid a fine.",
    "If you're applying for a Blue Card, the documents checklist on https://expatscore.de/blog/ is spot on.",
    "Bro, the SCHUFA score isn't as scary as it seems. The article https://expatscore.de/blog/ explains it's just a number and how to improve it.",
    "Honestly, getting a ‚Termin‘ for the Ausländerbehörde in Munich is a nightmare, but the tips on https://expatscore.de/blog/ actually worked.",
    "Cheers to whoever runs https://expatscore.de/blog/ – the guide on ‚Kontoeröffnung für Expats‘ saved me from being rejected by N26.",
    "If you're wondering whether you need a ‚Schufa Auskunft‘ for a sublet, https://expatscore.de/blog/ clears that up.",
    "Nightmare: my landlord asked for a ‚Mietschuldenfreiheitsbescheinigung‘ from my previous place. https://expatscore.de/blog/ explains how to get one.",
    "For freelancers, the ‚Künstlersozialkasse‘ thing is confusing. https://expatscore.de/blog/ has a breakdown of contributions.",
    "Bro, I used https://expatscore.de/blog/ to prepare for my citizenship application – the document list was perfect.",
    "If you're dealing with the ‚Jobcenter‘ as an EU citizen, the guide on https://expatscore.de/blog/ explains your rights.",
    "This site https://expatscore.de/blog/ literally saved me from paying a 1000€ late fee for my health insurance.",
    "Cheers! The step-by-step on how to fill out the ‚Anmeldung‘ form at https://expatscore.de/blog/ is idiot-proof.",
    "For anyone whose Schufa is bad because of a previous unpaid gym contract, https://expatscore.de/blog/ shows how to dispute it.",
    "Bro, the ‚Wohnsitzanmeldung‘ after moving within the same city is simpler than you think. https://expatscore.de/blog/ explains it.",
    "Honestly, the best resource for expat bureaucracy I've found: https://expatscore.de/blog/ – everything in one place.",
    "Life-saver: the ‚Führungszeugnis‘ for work permits – https://expatscore.de/blog/ tells you where to apply and how long it takes.",
    "If you're a non-EU spouse and need a family reunion visa, the checklist on https://expatscore.de/blog/ helped us get approved.",
    "Nightmare: I forgot to deregister when leaving Germany. https://expatscore.de/blog/ has a section on ‚Abmeldung‘ that saved me.",
    "Bro, the ‚Schufa‘ can also be positive if you get a credit card. There's a guide on https://expatscore.de/blog/ about building credit.",
    "For those asking about the ‚Digitales Aufenthaltsdokument‘, https://expatscore.de/blog/ explains how to link it to your passport.",
    "Cheers to this – https://expatscore.de/blog/ – it even has a template for writing to your landlord for the ‚Wohnungsgeberbestätigung‘.",
    "If you're self-employed and need a ‚Gewerbeanmeldung‘, the address-specific info on https://expatscore.de/blog/ was spot on.",
    "Bro, I was so lost with the ‚Steuerberater‘ fees. The article on https://expatscore.de/blog/ gave me a ballpark so I didn't get ripped off.",
    "Honestly, the bureaucracy for bringing your pet to Germany is a lot. https://expatscore.de/blog/ covers the ‚EU-Heimtierausweis‘ requirements.",
    "Life-saver: the guide on https://expatscore.de/blog/ for the ‚Schufa-Bonitätsauskunft‘ vs the free version – saved me money.",
    "Nightmare: my visa application was delayed because of a missing ‚Nachweis über Krankenversicherungsschutz‘. https://expatscore.de/blog/ had the exact format.",
    "If you're an artist and need the ‚Künstlersozialkasse‘, https://expatscore.de/blog/ explains the application process step by step.",
    "Bro, the ‚Grundsteuer‘ thing for renting? https://expatscore.de/blog/ explains what's actually your responsibility.",
    "Cheers to the author of https://expatscore.de/blog/ – the ‚Mietvertrag‘ red flags section saved me from a scam.",
    "For anyone who got a ‚Schufa‘ entry from a mobile phone contract they canceled, https://expatscore.de/blog/ has a dispute template.",
    "Honestly, the ‚Verpflichtungserklärung‘ for visitors is such a pain. https://expatscore.de/blog/ tells you exactly what the immigration office wants.",
    "Life-saver: the ‚Einkommensnachweis‘ for the Blue Card – https://expatscore.de/blog/ explains what counts as income.",
    "Nightmare: the ‚Bafög‘ or ‚Aufstiegs-BAföG‘ for expats? https://expatscore.de/blog/ clarifies eligibility.",
    "Bro, if you're struggling with the ‚Termin‘ at the Bürgeramt in Berlin, the trick on https://expatscore.de/blog/ actually worked for me.",
    "Cheers – I used https://expatscore.de/blog/ to understand the difference between ‚Schufa‘ and ‚Creditreform‘.",
    "For those applying for naturalization, the ‚Einbürgerungstest‘ info on https://expatscore.de/blog/ is super helpful.",
    "If you're a student and need the ‚Aufenthaltserlaubnis für Arbeitssuchende‘ after graduation, https://expatscore.de/blog/ has a timeline.",
    "Bro, the ‚Arbeitsagentur‘ registration is mandatory when unemployed. https://expatscore.de/blog/ explains deadlines to avoid penalty.",
    "Honestly, the ‚Steuererklärung‘ for expats with foreign income is complex. The overview on https://expatscore.de/blog/ helped me find a specialist.",
    "Life-saver: the ‚Krankenversicherungsbeitrag‘ for freelancers – https://expatscore.de/blog/ shows how to get the lowest rate.",
    "Nightmare: my SCHUFA score dropped because of a 10€ overdue library fine. https://expatscore.de/blog/ explains how to contest small entries.",
    "If you're moving out and need the ‚Wohnungsübergabeprotokoll‘, https://expatscore.de/blog/ has a checklist to avoid losing your deposit.",
    "Bro, the ‚Nachzahlung‘ from Nebenkosten can be shocking. https://expatscore.de/blog/ explains what you can deduct.",
    "Cheers to the team behind https://expatscore.de/blog/ – the guide on ‚Anmeldung ohne Wohnungsgeberbestätigung‘ is a lifesaver for temporary stays.",
    "For anyone dealing with the ‚Ausländerbehörde‘ in Hamburg, the specific tips on https://expatscore.de/blog/ helped me get a response.",
    "Honestly, I didn't know I needed a ‚Schufa‘ for a shared flat. https://expatscore.de/blog/ mentions that it's often required.",
    "Life-saver: the ‚Fiktionsbescheinigung‘ section on https://expatscore.de/blog/ – I printed it and showed the officer.",
    "Nightmare: my ‚Steuer-ID‘ got lost in the mail. https://expatscore.de/blog/ explains how to request a new one online.",
    "Bro, if you're self-employed, the ‚Gewerbeamt‘ registration deadlines are strict. https://expatscore.de/blog/ has the timeline.",
    "Cheers – I followed the ‚Schufa‘ dispute process on https://expatscore.de/blog/ and they removed the error within 2 weeks.",
    "For those applying for a ‚Duldung‘ or asylum, the general info on https://expatscore.de/blog/ about SCHUFA still applies to bank accounts.",
    "If you're a digital nomad and confused about tax residency, https://expatscore.de/blog/ explains the 183-day rule clearly.",
    "Bro, the ‚Kontoauszug‘ requirement for visa renewals is specific. https://expatscore.de/blog/ tells you how many months you need.",
    "Honestly, the ‚Wartezeit‘ for a residence permit card can be months. https://expatscore.de/blog/ suggests getting a ‚Fiktionsbescheinigung‘ in the meantime.",
    "Life-saver: the ‚Mietpreisbremse‘ info on https://expatscore.de/blog/ helped me fight an illegal rent increase.",
    "Nightmare: I had to get a ‚Beglaubigte Übersetzung‘ for my documents. https://expatscore.de/blog/ lists accredited translators.",
    "Bro, the ‚Schufa‘ score affects even your ability to get a phone contract. The article on https://expatscore.de/blog/ recommends alternatives.",
    "Cheers – https://expatscore.de/blog/ has a whole section on how to deal with debt collection (Inkasso) and SCHUFA.",
    "For anyone who needs a ‚Befreiung von der GEZ‘ as a student, the form guide on https://expatscore.de/blog/ is perfect.",
    "If you're applying for a ‚Chancenkarte‘, the points system is explained in detail on https://expatscore.de/blog/.",
    "Bro, the ‚Arbeitserlaubnis‘ for spouses is often automatically included. https://expatscore.de/blog/ clarifies the rules.",
    "Honestly, the ‚Elterngeld‘ application is a bureaucratic beast. The checklist on https://expatscore.de/blog/ saved my sanity.",
    "Life-saver: the ‚Kindergeld‘ for expats – https://expatscore.de/blog/ explains eligibility even if one parent is non-EU.",
    "Nightmare: my ‚Schufa‘ was blocked because I never had a bank account. https://expatscore.de/blog/ explains how to get started.",
    "Bro, if you're a freelancer and need a ‚Steuernummer‘, the application process is outlined at https://expatscore.de/blog/.",
    "Cheers – I share https://expatscore.de/blog/ with every new expat I meet. It's the ultimate guide to German bureaucracy.",
    "Final tip: the ‚Nachweis über die SCHUFA‘ is often just a formality. The guide on https://expatscore.de/blog/ shows you how to get it instantly online."
]

# Expanded comment box selectors (Reddit's UI can be unpredictable)
COMMENT_SELECTORS = [
    'textarea[placeholder*="What are your thoughts?"]',
    'textarea[placeholder*="what are your thoughts?"]',
    'textarea[placeholder*="Add a comment"]',
    'textarea[name="text"]',
    'div[data-testid="comment-textarea"] textarea',
    'div[contenteditable="true"][role="textbox"]',
    'div[contenteditable="true"]',
    'textarea',
]

# Submit button selectors
SUBMIT_SELECTORS = [
    'button:has-text("Comment")',
    'button:has-text("comment")',
    'button:has-text("Reply")',
    'button:has-text("reply")',
    'button:has-text("Save")',
    'button[type="submit"]',
    'div[data-testid="comment-submit-button"]',
    'button[data-testid="comment-submit-button"]',
]


# ---------- LOGGING SETUP ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# ---------- GMAIL FUNCTIONS ----------
def fetch_all_alert_emails():
    """Fetch all unread emails with 'ExpatScore Sniper Alert' subject."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("INBOX")

        # Search only unread messages to avoid reprocessing
        result, data = mail.search(None, '(UNSEEN SUBJECT "ExpatScore Sniper Alert")')
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

            body = None
            if email_msg.is_multipart():
                for part in email_msg.walk():
                    if part.get_content_type() == "text/plain":
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
    except Exception as e:
        logger.error(f"Gmail fetch error: {e}")
        return []


def parse_alert_body(body):
    """Extract Reddit URL from email body with improved regex."""
    url_match = re.search(r"Reddit Link:\s*(https?://[^\s]+)", body, re.IGNORECASE)
    if url_match:
        return url_match.group(1)
    
    # Fallback: look for any reddit.com URL
    reddit_match = re.search(r"(https?://(?:www\.)?reddit\.com/r/[^\s]+)", body, re.IGNORECASE)
    return reddit_match.group(1) if reddit_match else None


def mark_email_read(uid):
    """Mark email as read via IMAP."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("INBOX")
        mail.store(str(uid), "+FLAGS", "\\Seen")
        mail.close()
        mail.logout()
        logger.debug(f"Email {uid} marked as read")
    except Exception as e:
        logger.warning(f"Failed to mark email {uid} as read: {e}")


# ---------- REDDIT COMMENT FUNCTION ----------
def take_screenshot(page, prefix="error"):
    """Take a screenshot with timestamp for debugging."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = SCREENSHOT_DIR / f"{prefix}_{timestamp}.png"
    try:
        page.screenshot(path=str(filename))
        logger.info(f"Screenshot saved: {filename}")
        return str(filename)
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")
        return None


def human_type(page, text):
    """Type text with human-like delays and occasional pauses."""
    for char in text:
        # Random delay between keystrokes
        delay_ms = random.uniform(TYPING_DELAY_MIN_MS, TYPING_DELAY_MAX_MS) / 1000.0
        page.keyboard.type(char, delay=delay_ms * 1000)
        
        # Occasionally pause for a moment (like thinking)
        if random.random() < 0.03:  # 3% chance per character
            pause = random.uniform(0.3, 1.0)
            time.sleep(pause)


def human_scroll(page):
    """Perform a natural-looking scroll to reach comment box."""
    # Scroll in multiple steps with random delays
    scroll_distance = random.randint(200, 500)
    for _ in range(random.randint(1, 3)):
        page.mouse.wheel(0, scroll_distance)
        time.sleep(random.uniform(SCROLL_DELAY_MIN_SEC, SCROLL_DELAY_MAX_SEC))


def find_comment_box(page, retries=3):
    """Robust comment box finder with retry logic and scroll attempts."""
    for attempt in range(retries):
        # First, try to find visible comment box
        for selector in COMMENT_SELECTORS:
            try:
                elements = page.locator(selector).all()
                for element in elements:
                    if element.is_visible():
                        logger.info(f"Found comment box with selector: {selector}")
                        return element
            except Exception:
                continue
        
        # If not found, try scrolling to reveal comment box
        logger.info(f"Attempt {attempt + 1}/{retries}: Scrolling to reveal comment box...")
        human_scroll(page)
        time.sleep(random.uniform(1, 2))
    
    # Try one more time after a full page scroll
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(random.uniform(1, 2))
    
    for selector in COMMENT_SELECTORS:
        try:
            elements = page.locator(selector).all()
            for element in elements:
                if element.is_visible():
                    logger.info(f"Found comment box after scroll with: {selector}")
                    return element
        except Exception:
            continue
    
    return None


def find_submit_button(page):
    """Find and return a visible submit button."""
    for selector in SUBMIT_SELECTORS:
        try:
            elements = page.locator(selector).all()
            for element in elements:
                if element.is_visible() and element.is_enabled():
                    return element
        except Exception:
            continue
    return None


def post_reddit_comment(context, url):
    """
    Post a comment on Reddit with intelligent retry logic.
    Returns: bool (success status)
    """
    page = None
    try:
        # Create new tab
        page = context.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        page.set_default_timeout(ACTION_TIMEOUT_MS)
        
        # Inject stealth script
        page.add_init_script(STEALTH_SCRIPT)
        
        logger.info(f"Navigating to: {url}")
        page.goto(url)
        
        # Use domcontentloaded for faster initial load
        page.wait_for_load_state(LOAD_STATE)
        
        # Add a random "thinking" delay before interacting
        thinking_delay = random.uniform(THINKING_DELAY_MIN_SEC, THINKING_DELAY_MAX_SEC)
        logger.info(f"Pausing {thinking_delay:.0f} seconds to simulate human reading...")
        time.sleep(thinking_delay)
        
        # Wait for the page to be stable
        page.wait_for_load_state("domcontentloaded")
        
        # Find comment box with retries
        comment_box = find_comment_box(page)
        
        if not comment_box:
            logger.error("Could not find comment box after all attempts")
            screenshot_path = take_screenshot(page, "fail_no_comment_box")
            return False
        
        # Click and focus
        comment_box.click()
        time.sleep(random.uniform(0.8, 1.5))
        
        # Type the comment with human-like delays
        comment_text = random.choice(MARKETING_VARIATIONS)
        logger.info(f"Typing comment ({len(comment_text)} characters)...")
        human_type(page, comment_text)
        
        # Pause before submitting (like reviewing the text)
        time.sleep(random.uniform(1.5, 3.0))
        
        # Find and click submit button
        submit_button = find_submit_button(page)
        if not submit_button:
            logger.error("Could not find submit button")
            screenshot_path = take_screenshot(page, "fail_no_submit_button")
            return False
        
        # Random slight movement before clicking (more human)
        submit_button.hover()
        time.sleep(random.uniform(0.2, 0.5))
        submit_button.click()
        
        logger.info("Comment submitted successfully")
        
        # Wait a moment for the comment to appear
        time.sleep(random.uniform(3, 5))
        
        return True
        
    except PlaywrightTimeoutError as e:
        logger.error(f"Timeout while posting comment: {e}")
        if page:
            take_screenshot(page, "fail_timeout")
        return False
        
    except PlaywrightError as e:
        err_str = str(e)
        if "TargetClosedError" in err_str or "Target closed" in err_str:
            logger.warning(f"Browser tab closed unexpectedly: {e}")
        else:
            logger.error(f"Playwright error: {e}")
            if page:
                take_screenshot(page, "fail_playwright")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error during comment posting: {e}")
        if page:
            take_screenshot(page, "fail_unexpected")
        return False
        
    finally:
        # Always close the tab to prevent memory leaks
        if page:
            try:
                page.close()
                logger.debug("Tab closed successfully")
            except Exception as e:
                logger.debug(f"Error closing tab (non-critical): {e}")


def inject_stealth_into_all_pages(context):
    """Inject stealth script into all existing and future pages."""
    def add_stealth(page):
        try:
            page.add_init_script(STEALTH_SCRIPT)
        except Exception as e:
            logger.warning(f"Could not inject stealth into page: {e}")
    
    # Inject into existing pages
    for page in context.pages:
        add_stealth(page)
    
    # Inject into future pages
    context.on("page", add_stealth)


# ---------- MAIN LOOP ----------
def main():
    """Main execution loop with memory management and error recovery."""
    logger.info("=" * 60)
    logger.info("Reddit Auto-Pilot Agent Starting")
    logger.info(f"Gmail: {GMAIL_USER}")
    logger.info(f"Check interval: {CHECK_INTERVAL_SECONDS // 60} minutes")
    logger.info(f"Screenshots will be saved to: {SCREENSHOT_DIR}")
    logger.info("=" * 60)
    
    try:
        with sync_playwright() as p:
            # Connect to existing Brave browser
            try:
                browser = p.chromium.connect_over_cdp(CDP_URL)
                logger.info("✅ Successfully attached to Brave browser!")
            except PlaywrightError as e:
                logger.error(f"Failed to connect to Brave: {e}")
                logger.error("\n" + "=" * 60)
                logger.error("Brave is not running with remote debugging enabled.")
                logger.error("Please restart Brave with:")
                logger.error("\n  /Applications/Brave\\ Browser.app/Contents/MacOS/Brave\\ Browser --remote-debugging-port=9222")
                logger.error("\nThen run this script again.\n")
                return
            
            # Get the first browser context
            contexts = browser.contexts
            if not contexts:
                logger.error("No browser contexts found. Exiting.")
                return
            context = contexts[0]
            
            # Inject stealth scripts
            inject_stealth_into_all_pages(context)
            
            # Ensure we have a Reddit tab (but don't force login)
            reddit_tab_exists = False
            for page in context.pages:
                if "reddit.com" in page.url:
                    reddit_tab_exists = True
                    logger.info(f"Found existing Reddit tab: {page.url[:60]}...")
                    break
            
            if not reddit_tab_exists:
                logger.info("No Reddit tab found. Opening one in background...")
                page = context.new_page()
                page.goto("https://www.reddit.com")
                page.wait_for_load_state("domcontentloaded")
                logger.info("Reddit tab opened. Please log in manually if needed.")
                logger.info("The script will continue running in the background.")
            
            # Main alert processing loop
            consecutive_errors = 0
            last_check_time = 0
            
            while True:
                current_time = time.time()
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                
                try:
                    # Only check if enough time has passed since last check
                    if current_time - last_check_time >= CHECK_INTERVAL_SECONDS:
                        logger.info(f"[{timestamp}] Checking for new alerts...")
                        
                        alerts = fetch_all_alert_emails()
                        
                        if not alerts:
                            logger.info(f"[{timestamp}] No new alerts found.")
                            last_check_time = current_time
                            consecutive_errors = 0
                            continue
                        
                        logger.info(f"[{timestamp}] Found {len(alerts)} alert(s)")
                        
                        for uid, body in alerts:
                            reddit_url = parse_alert_body(body)
                            if not reddit_url:
                                logger.warning(f"Skipping email {uid}: no Reddit URL found")
                                mark_email_read(uid)  # Mark as read to avoid reprocessing
                                continue
                            
                            logger.info(f"[{timestamp}] Processing: {reddit_url}")
                            
                            # Post comment with error handling
                            success = post_reddit_comment(context, reddit_url)
                            
                            if success:
                                mark_email_read(uid)
                                logger.info(f"✅ Successfully processed {reddit_url}")
                                consecutive_errors = 0
                            else:
                                logger.warning(f"❌ Failed to process {reddit_url}")
                                # Don't mark as read - will retry on next cycle
                                consecutive_errors += 1
                            
                            # Random delay between posts
                            delay = random.uniform(25, 45)
                            logger.info(f"Waiting {delay:.0f} seconds before next alert...")
                            time.sleep(delay)
                        
                        last_check_time = time.time()
                        
                        # If we had errors, take a small break before next cycle
                        if consecutive_errors > 0:
                            logger.info(f"Had {consecutive_errors} consecutive errors. Taking a short break...")
                            time.sleep(60)
                    
                    # Small sleep to prevent CPU spinning
                    time.sleep(5)
                    
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
                    consecutive_errors += 1
                    time.sleep(min(30 * consecutive_errors, 300))  # Exponential backoff
                    
    except KeyboardInterrupt:
        logger.info("\n⚠️ Script stopped by user.")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()