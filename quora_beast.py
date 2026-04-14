#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  sniper.py – ExpatScore Intelligence v20 "Tor-Stable Sniper"                 ║
║  ExpatScore.de | Universal Lead Hunter (Quora + Reddit + Anywhere)           ║
║  HOTFIX: Tor Stability + Hybrid Mode + DOMContentLoaded                      ║
║                                                                              ║
║  Critical Fixes (v20):                                                       ║
║    • wait_until="domcontentloaded" (fixes Browser closed errors)             ║
║    • Default timeout 90s (page.set_default_timeout(90000))                   ║
║    • Hybrid Mode: Hardcoded Hard-Seeds fallback for "germany banking"        ║
║    • Tor Stability: 10s sleep after NEWNYM signal                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
import time
from collections import deque
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Deque
from urllib.parse import quote

from loguru import logger
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page, TimeoutError as PWTimeout
from stem import Signal
from stem.control import Controller

# ==================================================================
#  CONSTANTS (v20 Tor-Stable + Hybrid Mode)
# ==================================================================
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

TOR_SOCKS_HOST = "127.0.0.1"
TOR_SOCKS_PORT = 9050
TOR_CONTROL_PORT = 9051

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

MAX_AGE_DAYS = 365
BROWSER_RESTART_EVERY = 3              # Full wipe every 3 visits (8GB Mac stability)
ROTATE_EVERY_PAGES = 3
THINKING_TIME_MIN = 30.0               # Human "thinking" time between visits
THINKING_TIME_MAX = 60.0
MAX_URLS_PER_NICHE = 200
SCROLL_ATTEMPTS = 4

# Multi-Search Engine Matrix for universal hunting
SEARCH_ENGINES = [
    {"name": "google", "base": "https://www.google.com/search?q={query}"},
    {"name": "bing", "base": "https://www.bing.com/search?q={query}"},
    {"name": "duckduckgo", "base": "https://duckduckgo.com/?q={query}"},
    {"name": "ecosia", "base": "https://www.ecosia.org/search?q={query}"},
]

REFERERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://t.co/",
]

# High-intent verification keywords (Germany expat banking/visa focus)
VERIFICATION_KEYWORDS = ["germany", "blocked account", "visa", "bank", "expat", "fintiba", "expatrio", "coracle", "anmeldung", "student visa"]

# ==================================================================
#  HYBRID MODE: Hardcoded Hard-Seeds for Critical Niches
# ==================================================================
HARD_SEEDS = {
    "germany banking": [
        "https://www.quora.com/topic/Blocked-Accounts-for-Germany",
        "https://www.quora.com/topic/Expatriates-in-Germany", 
        "https://www.reddit.com/r/germany/search/?q=blocked%20account",
        "https://www.reddit.com/r/germany/search/?q=bank%20account%20refused",
        "https://www.reddit.com/r/germany/search/?q=schufa",
        "https://www.quora.com/search?q=germany+bank+account+expat",
        "https://www.quora.com/search?q=blocked+account+germany+visa",
    ],
    "default": [
        "https://www.quora.com/search?q=expat+banking+europe",
        "https://www.reddit.com/r/expats/search/?q=germany+bank",
    ]
}

console = Console()

# ==================================================================
#  LOGURU SETUP
# ==================================================================
logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:8}</level> | <cyan>{message}</cyan>",
    backtrace=True,
    diagnose=True,
)

# ==================================================================
#  TOR MANAGER (v20: 10s Stability Sleep)
# ==================================================================
class TorManager:
    def __init__(self, socks_host: str = TOR_SOCKS_HOST, socks_port: int = TOR_SOCKS_PORT,
                 control_port: int = TOR_CONTROL_PORT):
        self.socks_host = socks_host
        self.socks_port = socks_port
        self.control_port = control_port
        self.current_ip: Optional[str] = None
        self.rotation_count = 0

    @property
    def proxy_string(self) -> str:
        return f"socks5://{self.socks_host}:{self.socks_port}"

    def get_current_ip(self) -> Optional[str]:
        import requests
        try:
            proxies = {"http": self.proxy_string, "https": self.proxy_string}
            resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=15)
            if resp.status_code == 200:
                self.current_ip = resp.json().get("ip")
                return self.current_ip
        except Exception as e:
            logger.debug(f"IP check failed: {e}")
        return None

    def rotate_circuit(self) -> bool:
        old_ip = self.get_current_ip() or "N/A"
        try:
            with Controller.from_port(port=self.control_port) as ctrl:
                ctrl.authenticate()
                ctrl.signal(Signal.NEWNYM)
                self.rotation_count += 1
                logger.info(f"🔄 NEWNYM signal sent (#{self.rotation_count})")
            
            # v20 FIX: 10 second stabilization period for Tor circuit
            logger.info("⏱️  Stabilizing Tor circuit (10s)...")
            time.sleep(10)
            
            new_ip = self.get_current_ip()
            if new_ip and new_ip != old_ip:
                logger.success(f"✅ Tor identity verified – New exit IP: {new_ip}")
                time.sleep(5)
                return True
            else:
                logger.warning(f"⚠️ NEWNYM sent but IP unchanged")
                time.sleep(5)
                return False
        except Exception as e:
            logger.warning(f"Tor rotation failed: {e}")
            time.sleep(5)
            return False

    def ensure_fresh_ip(self) -> bool:
        for attempt in range(5):
            if self.rotate_circuit():
                return True
            time.sleep(3)
        logger.warning("❌ Failed to obtain fresh IP – continuing anyway")
        return False


# ==================================================================
#  DATE ENGINE
# ==================================================================
class DateEngine:
    @staticmethod
    def parse_asked_text(text: str) -> Optional[datetime]:
        if not text:
            return None
        text = text.lower().strip()
        match = re.search(r'(\d+)\s+(year|years|month|months|day|days)\s+ago', text)
        if match:
            num = int(match.group(1))
            unit = match.group(2)
            now = datetime.now(UTC)
            if 'year' in unit:
                return now.replace(year=now.year - num)
            elif 'month' in unit:
                year = now.year - (num // 12)
                month = now.month - (num % 12)
                if month <= 0:
                    month += 12
                    year -= 1
                return datetime(year, month, now.day, tzinfo=UTC)
            elif 'day' in unit:
                return now - timedelta(days=num)
        match_abs = re.search(r'asked on\s+([a-z]+)\s+(\d{1,2}),\s+(\d{4})', text)
        if match_abs:
            month_name = match_abs.group(1).capitalize()
            day = int(match_abs.group(2))
            year = int(match_abs.group(3))
            try:
                months = {"January":1, "February":2, "March":3, "April":4, "May":5, "June":6,
                          "July":7, "August":8, "September":9, "October":10, "November":11, "December":12}
                return datetime(year, months.get(month_name, 1), day, tzinfo=UTC)
            except:
                pass
        return None

    @staticmethod
    def is_fresh(date_obj: Optional[datetime]) -> bool:
        if not date_obj:
            return False
        return (datetime.now(UTC) - date_obj).days <= MAX_AGE_DAYS


# ==================================================================
#  STATE TRACKER
# ==================================================================
class StateTracker:
    def __init__(self, path: Path = DATA_DIR / "seen_urls.json"):
        self.path = path
        self.seen: Set[str] = set()
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.seen = set(data.get("urls", []))
                logger.info(f"✅ Loaded {len(self.seen)} previously seen URLs")
            except Exception as e:
                logger.warning(f"Failed to load seen URLs: {e}")

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({
                    "urls": list(self.seen),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "total_seen": len(self.seen)
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save seen URLs: {e}")

    def is_seen(self, url: str) -> bool:
        normalized = url.split("?")[0].rstrip("/")
        return normalized in self.seen

    def mark_seen(self, url: str):
        normalized = url.split("?")[0].rstrip("/")
        if normalized not in self.seen:
            self.seen.add(normalized)
            self._save()


# ==================================================================
#  MULTI-PLATFORM SAVER
# ==================================================================
class MultiPlatformSaver:
    def __init__(self):
        self.paths = {
            "quora": (DATA_DIR / "quora.json", DATA_DIR / "quora.csv"),
            "reddit": (DATA_DIR / "reddit.json", DATA_DIR / "reddit.csv"),
            "others": (DATA_DIR / "others.json", DATA_DIR / "others.csv"),
        }
        for platform in self.paths:
            self._init_csv(platform)

    def _init_csv(self, platform: str):
        csv_path = self.paths[platform][1]
        if not csv_path.exists():
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "niche", "platform", "title", "url", "snippet", "extracted_at"])

    def save(self, lead: Dict, platform: str):
        if platform not in self.paths:
            platform = "others"
        json_path, csv_path = self.paths[platform]
        lead["extracted_at"] = datetime.now(UTC).isoformat()
        with open(json_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(lead, ensure_ascii=False) + "\n")
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                lead.get("timestamp", ""),
                lead.get("niche", ""),
                platform,
                lead.get("title", ""),
                lead.get("url", ""),
                lead.get("snippet", "")[:300],
                lead.get("extracted_at", "")
            ])
        logger.success(f"💾 Saved {platform} lead → {lead['title'][:60]}...")


# ==================================================================
#  STEALTH BROWSER (v20: 90s Timeout + DOMContentLoaded)
# ==================================================================
class StealthBrowser:
    def __init__(self, tor_proxy: str, headless: bool = True):
        self.tor_proxy = tor_proxy
        self.headless = headless
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.url_count = 0

    def start(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            proxy={"server": self.tor_proxy},
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-setuid-sandbox",
                "--disable-features=IsolateOrigins,site-per-process",
                "--max_old_space_size=512",
            ]
        )
        self._new_context()

    def _new_context(self):
        if self.context:
            try:
                self.context.close()
            except:
                pass
        ua = random.choice(USER_AGENTS)
        viewport = {"width": random.randint(1280, 1440), "height": random.randint(800, 960)}
        self.context = self.browser.new_context(
            user_agent=ua,
            viewport=viewport,
            locale="en-US",
            timezone_id="Europe/Berlin",
            java_script_enabled=True,
            bypass_csp=True,
        )
        self.context.clear_cookies()
        self.context.clear_permissions()
        
        # v20 FIX: Create page and set default timeout to 90 seconds
        self.page = self.context.new_page()
        self.page.set_default_timeout(90000)  # 90 seconds
        
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            window.chrome = {runtime: {}};
        """)
        
        # Block unnecessary assets to speed up loading
        def block_assets(route):
            url = route.request.url.lower()
            if any(ext in url for ext in ['.png','.jpg','.jpeg','.gif','.svg','.woff','.ttf','ads','analytics','tracking']):
                route.abort()
            else:
                route.continue_()
        self.page.route("**/*", block_assets)
        self.url_count = 0

    def full_restart(self):
        logger.info("🧹 Full memory & session purge")
        self.close()
        self.start()

    def ensure_fresh_context(self, urls_processed: int):
        if urls_processed > 0 and urls_processed % BROWSER_RESTART_EVERY == 0:
            logger.info(f"🔄 MacGuard: Full browser wipe after {urls_processed} visits")
            self.full_restart()

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def simulate_human_behavior(self):
        for _ in range(random.randint(2, 5)):
            self.page.mouse.move(random.randint(50, 1300), random.randint(50, 800), steps=random.randint(5, 10))
            time.sleep(random.uniform(0.3, 0.9))
        if random.random() < 0.5:
            self.page.evaluate("window.scrollBy(0, Math.random() * 700 + 150)")


# ==================================================================
#  INTELLIGENCE ENGINE (v20: DOMContentLoaded + Hybrid Fallback)
# ==================================================================
class IntelligenceEngine:
    @staticmethod
    def is_relevant(text: str, niche: str) -> bool:
        combined = (text or "").lower()
        niche_words = niche.lower().split()
        return any(k in combined for k in VERIFICATION_KEYWORDS) or any(w in combined for w in niche_words)

    @staticmethod
    def perform_universal_search(page: Page, niche: str) -> List[str]:
        """Search multiple engines and collect any URLs (no site: limit)."""
        urls: Set[str] = set()
        
        for engine in SEARCH_ENGINES:
            query = f"{niche} reviews 2026" if random.random() > 0.5 else niche
            encoded = quote(query)
            search_url = engine["base"].format(query=encoded)
            logger.info(f"🔍 Hunting via {engine['name'].upper()} → {search_url}")
            try:
                # v20 FIX: Changed wait_until to "domcontentloaded" for Tor stability
                page.goto(search_url, referer=random.choice(REFERERS), wait_until="domcontentloaded", timeout=90000)
                time.sleep(random.uniform(4, 8))
                for _ in range(SCROLL_ATTEMPTS):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(random.uniform(1, 2))
                locator = page.locator('a[href^="http"]')
                elements = locator.all()
                if elements and len(elements) > 0:
                    for elem in elements[:15]:  # limit per engine
                        href = elem.get_attribute("href")
                        if href and href.startswith("http") and len(href) > 30:
                            if "quora.com" in href or "reddit.com" in href or True:
                                urls.add(href)
            except Exception as e:
                logger.warning(f"Search on {engine['name']} failed (safe skip): {e}")
        
        # v20 FIX: Hybrid Mode - Fallback to Hard Seeds if no URLs found
        if len(urls) == 0:
            logger.warning("⚠️  Universal search returned 0 results. Activating HYBRID MODE with Hard Seeds...")
            normalized_niche = niche.lower().strip()
            
            if normalized_niche in HARD_SEEDS:
                hard_urls = HARD_SEEDS[normalized_niche]
                logger.info(f"🌱 Injecting {len(hard_urls)} Hard Seeds for '{normalized_niche}'")
                urls.update(hard_urls)
            else:
                # Try partial match
                for key, seeds in HARD_SEEDS.items():
                    if key in normalized_niche or normalized_niche in key:
                        logger.info(f"🌱 Injecting {len(seeds)} Hard Seeds for partial match '{key}'")
                        urls.update(seeds)
                        break
                else:
                    # Default fallback
                    logger.info(f"🌱 Injecting {len(HARD_SEEDS['default'])} Default Hard Seeds")
                    urls.update(HARD_SEEDS["default"])
        
        logger.success(f"🌐 Universal search collected {len(urls)} candidate URLs for niche '{niche}'")
        return list(urls)

    @staticmethod
    def scrape_quora(page: Page, url: str) -> Optional[Dict]:
        try:
            page.wait_for_selector("h1", timeout=15000)
            title = page.title() or ""
            asked_text = ""
            for elem in page.query_selector_all("span, div, p, time"):
                txt = elem.inner_text().strip()
                if "asked" in txt.lower() and len(txt) < 180:
                    asked_text = txt
                    break
            date_obj = DateEngine.parse_asked_text(asked_text)
            snippet = page.evaluate("document.body.innerText")[:1200] if page else ""
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "niche": "",
                "platform": "quora",
                "title": title[:500],
                "url": url,
                "snippet": snippet,
                "asked_date": date_obj.isoformat() if date_obj else "",
            }
        except Exception as e:
            logger.debug(f"Quora scrape error: {e}")
            return None

    @staticmethod
    def scrape_reddit(page: Page, url: str) -> Optional[Dict]:
        try:
            page.wait_for_selector("h1", timeout=15000)
            title = page.title() or ""
            snippet = ""
            try:
                post_text = page.locator('[data-testid="post-text"]').first.inner_text(timeout=5000)
                snippet = post_text
            except:
                snippet = page.evaluate("document.body.innerText")[:1200]
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "niche": "",
                "platform": "reddit",
                "title": title[:500],
                "url": url,
                "snippet": snippet,
                "asked_date": "",
            }
        except Exception as e:
            logger.debug(f"Reddit scrape error: {e}")
            return None

    @staticmethod
    def scrape_general(page: Page, url: str) -> Optional[Dict]:
        try:
            page.wait_for_selector("title", timeout=15000)
            title = page.title() or ""
            snippet = page.evaluate("document.body.innerText")[:1500]
            return {
                "timestamp": datetime.now(UTC).isoformat(),
                "niche": "",
                "platform": "others",
                "title": title[:500],
                "url": url,
                "snippet": snippet,
                "asked_date": "",
            }
        except Exception as e:
            logger.debug(f"General scrape error: {e}")
            return None


# ==================================================================
#  MAIN MULTI-PLATFORM SNIPER ORCHESTRATOR v20
# ==================================================================
class ExpatScoreSniper:
    def __init__(self, niche: str, headless: bool = True, max_urls: int = MAX_URLS_PER_NICHE):
        self.niche = niche
        self.headless = headless
        self.max_urls = max_urls
        self.tor = TorManager()
        self.state = StateTracker()
        self.saver = MultiPlatformSaver()
        self.engine = IntelligenceEngine()
        self.browser: Optional[StealthBrowser] = None
        self.total_leads = 0
        self.total_visited = 0

    def run(self):
        logger.info(f"🚀 Starting ExpatScore Intelligence v20 – Niche: {self.niche}")
        console.print(Panel.fit("🔥 EXPATSCORE INTELLIGENCE v20 – TOR-STABLE SNIPER 🔥", style="bold red"))

        self.tor.get_current_ip()
        self.tor.ensure_fresh_ip()

        self.browser = StealthBrowser(tor_proxy=self.tor.proxy_string, headless=self.headless)
        self.browser.start()

        # Step 1: Universal search across engines (with Hybrid fallback)
        candidate_urls = self.engine.perform_universal_search(self.browser.page, self.niche)
        new_urls = [u for u in candidate_urls if not self.state.is_seen(u)][:self.max_urls]

        logger.info(f"🧬 Queue ready with {len(new_urls)} fresh URLs to snipe")

        visited_count = 0
        table = Table(title=f"🔥 Sniper – {self.niche}", expand=True)
        table.add_column("Status", style="cyan")
        table.add_column("Visited", style="blue")
        table.add_column("Leads", style="green")
        table.add_column("Platform", style="yellow")
        table.add_column("Tor IP", style="magenta")

        with Live(table, refresh_per_second=2, console=console) as live:
            for url in new_urls:
                self.browser.ensure_fresh_context(visited_count)
                rotation_counter = visited_count
                if rotation_counter % ROTATE_EVERY_PAGES == 0:
                    self.tor.ensure_fresh_ip()

                try:
                    referer = random.choice(REFERERS)
                    # v20 FIX: Changed wait_until to "domcontentloaded" and timeout to 90s
                    self.browser.page.goto(url, referer=referer, wait_until="domcontentloaded", timeout=90000)
                    self.browser.simulate_human_behavior()

                    # Human thinking time
                    thinking = random.uniform(THINKING_TIME_MIN, THINKING_TIME_MAX)
                    logger.info(f"🧠 Thinking like a real researcher ({thinking:.1f}s)")
                    time.sleep(thinking)

                    # Auto-classify & scrape
                    if "quora.com" in url.lower():
                        platform = "quora"
                        lead = self.engine.scrape_quora(self.browser.page, url)
                    elif "reddit.com" in url.lower():
                        platform = "reddit"
                        lead = self.engine.scrape_reddit(self.browser.page, url)
                    else:
                        platform = "others"
                        lead = self.engine.scrape_general(self.browser.page, url)

                    if lead and self.engine.is_relevant(lead.get("snippet", "") + lead.get("title", ""), self.niche):
                        lead["niche"] = self.niche
                        self.saver.save(lead, platform)
                        self.total_leads += 1
                        console.print(f"  [green]★[/green] {platform.upper()} lead: {lead['title'][:55]}...")
                    else:
                        logger.debug(f"Skipped irrelevant URL: {url[:60]}")

                    self.state.mark_seen(url)
                    visited_count += 1
                    self.total_visited += 1

                    current_ip = self.tor.current_ip or "unknown"
                    table.rows.clear()
                    table.add_row(
                        "🔥 ACTIVE",
                        f"{visited_count}/{self.max_urls}",
                        f"{self.total_leads}",
                        platform.upper(),
                        current_ip
                    )
                    live.update(table)

                except Exception as e:
                    logger.warning(f"URL sniper failed {url[:60]}...: {e}")
                    visited_count += 1

                time.sleep(random.uniform(5, 12))

        self.browser.close()
        console.print(Panel(f"🎯 SNIPER MISSION COMPLETE\nTotal leads sniped: {self.total_leads}\nPlatforms covered: Quora, Reddit & Web", style="bold green"))


# ==================================================================
#  CLI ENTRY POINT
# ==================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="ExpatScore Intelligence v20 – Tor-Stable Sniper")
    parser.add_argument("--niche", type=str, required=True, help="Niche to hunt (e.g. 'germany banking')")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", dest="headless", action="store_false")
    parser.add_argument("--max-urls", type=int, default=MAX_URLS_PER_NICHE)
    args = parser.parse_args()

    sniper = ExpatScoreSniper(
        niche=args.niche,
        headless=args.headless,
        max_urls=args.max_urls
    )
    sniper.run()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]⚠️  Sniper interrupted by user – all data saved[/bold red]")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}", exc_info=True)
        sys.exit(1)