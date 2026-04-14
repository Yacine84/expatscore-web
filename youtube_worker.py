# =============================================================================
# youtube_worker.py — ExpatScore.de YouTube Comment Sniper
# Version: 1.3 | Deep Search & Channel Authority Edition
# =============================================================================
# Architecture Overview:
#
#   DISCOVERY (daily, 06:00)
#   ├── Path A: Keyword Search    → search.list   (100 units/query × 7 = 700 units)
#   └── Path B: Channel Radar     → channels.list (1 unit) + playlistItems.list
#                                   (1 unit/channel × N channels = ~10 units)
#
#   HARVEST (every ~3hrs, 11:00–01:00)
#   ├── Standard Videos  → commentThreads.list (75 comments, 1 unit/video)
#   └── Priority Videos  → commentThreads.list (200 comments, 1 unit/video)
#       └── Triggered by: Tier1 density ≥ PRIORITY_DENSITY_THRESHOLD
#                         OR published within DEEP_SCAN_MAX_VIDEO_AGE_DAYS
#
#   RELEVANCE PERSISTENCE (hot_video_cache.json)
#   └── Tracks per-video: tier1_density, harvest_count, is_priority, published_at
#       Updated after every harvest cycle. Priority videos re-harvested first.
#
# Quota budget (worst case, all features active):
#   Discovery:  700 (search) + ~15 (channels) = 715 units/day
#   Harvest:    ~35 standard + ~10 priority × 1 unit = ~45 units/harvest
#               4 harvests × 45 = 180 units/day
#   Total:      ~895 units/day (91% headroom on 10k limit)
# =============================================================================

import os
import json
import time
import random
import logging
import requests
from datetime import datetime, date, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from groq_scorer import score_lead

# =============================================================================
# CONFIGURATION
# =============================================================================

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "YOUR_YOUTUBE_API_KEY_HERE")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "YOUR_N8N_WEBHOOK_URL_HERE")

# =============================================================================
# 📡 MONITORED CHANNELS — "Authority Radar"
#
# Curated channels where expats in Germany comment about financial pain.
# Selected for: comment density, expat audience, Schufa/banking topic coverage.
#
# TWO FORMATS SUPPORTED — use whichever you have:
#   {"name": "...", "handle": "@ChannelHandle"}   ← preferred, auto-resolved
#   {"name": "...", "id":     "UCxxxxxxxxxx"}      ← direct, no resolution needed
#
# Handle resolution: on first run, the bot calls channels.list(forHandle=...)
# (cost: 1 unit) and permanently caches the resulting channel ID.
# Subsequent runs use the cached ID — zero extra API cost.
#
# Cost per channel per harvest: 1 unit (playlistItems.list)
# vs keyword search: 100 units per query — 100× cheaper
# =============================================================================

MONITORED_CHANNELS = [
    # --- TIER 1: Primary targets — highest expat finance comment density ---
    {
        "name":   "Simple Germany",
        "handle": "@SimpleGermany",
        # Expat settlement guide — banking, Anmeldung, Schufa videos.
        # Comment sections are ground zero for "I just arrived and my bank rejected me."
    },
    {
        "name":   "My Life in Germany",
        "handle": "@MyLifeInGermany",
        # Hira's channel — South/Southeast Asian expat perspective.
        # Audience is overwhelmingly recent arrivals with zero Schufa history.
        # Highest Tier1 comment density of any channel in this niche.
    },
    {
        "name":   "Finanzfluss",
        "handle": "@Finanzfluss",
        # #1 German personal finance channel (~1M subs).
        # Schufa explainer videos have 100k+ views. Comment sections:
        # expats asking "but what if I just moved here and have no Schufa?"
    },
    {
        "name":   "PerFinEx",
        "handle": "@PerFinEx",
        # English-speaking independent financial advisor for expats in Germany.
        # Videos on health insurance, banking, pensions — audience is exactly
        # the professional expat who can't open a bank account. High CPA value.
    },
    # --- TIER 2: Secondary targets — large audiences, relevant comment traffic ---
    {
        "name":   "Easy German",
        "handle": "@EasyGerman",
        # 3M+ subscribers. Street interview format.
        # "How does Schufa work?" and "German banking explained" videos
        # attract massive newcomer traffic in comments.
    },
    {
        "name":   "Ahsan Finance",
        "handle": "@AhsanFinance",
        # English-language German personal finance for immigrants specifically.
        # ~31K subscribers but extremely tight niche match — audience IS your ICP.
    },
    {
        "name":   "HalloGermany",
        "handle": "@HalloGermany",
        # Expat onboarding — banking, bureaucracy, first steps in Germany.
        # "Just arrived" audience with high financial confusion signals.
    },
    {
        "name":   "Wanted Adventure",
        "handle": "@WantedAdventure",
        # Large expat lifestyle channel with Germany bureaucracy content.
        # High subscriber count = high comment volume = more leads per harvest.
    },
]

CHANNEL_VIDEOS_PER_FETCH = 8   # Latest N videos to pull from each channel per cycle

# =============================================================================
# 🎯 YOUTUBE SEARCH QUERIES — Discovery via search.list (100 units each)
# =============================================================================

YT_SEARCH_QUERIES = [
    "moving to Germany expat guide",
    "Germany bank account foreigners english",
    "Schufa explained expats",
    "Germany visa process english",
    "life in Germany newcomer tips",
    "Germany apartment search expat",
    "Germany health insurance expat guide",
]

# =============================================================================
# 🔬 TIER 1 — CRITICAL TRIGGERS
# Active rejection, desperation, financial emergency signals.
# Any single hit = routed directly to Groq. Lower score gate (35 vs 45).
#
# 🔑 NEW: German-English hybrid terms expats actually type when desperate.
# =============================================================================

YT_TIER1_TRIGGERS = [
    # --- Active Rejection (highest CPA signal) ---
    "bank rejected", "account denied", "n26 rejected", "n26 won't let me",
    "n26 blocked", "revolut blocked", "revolut frozen", "wise blocked",
    "blocked account", "account frozen", "account closed",
    "apartment rejected", "can't rent", "landlord refused", "rental rejected",
    "loan rejected", "kredit abgelehnt", "antrag abgelehnt",
    "schufa eintrag", "negative schufa", "schufa score 0", "keine schufa",
    "ohne schufa", "schufa problem", "konto abgelehnt", "girokonto abgelehnt",
    "fintiba problem", "expatrio problem", "fintiba rejected", "expatrio rejected",
    "bank refused", "rejected by", "they refused", "got rejected",

    # --- 🆕 German-English Hybrid Pain Terms ---
    "p-konto",                   # Pfändungsschutzkonto — garnishment protection account
    "p konto",
    "basiskonto",                # Basic account — legal right but hard to open
    "basis-konto",
    "schufa-auskunft",           # Official Schufa self-disclosure
    "schufa auskunft",
    "schufa eintrag löschen",    # Trying to delete Schufa entry
    "schufa löschen",
    "finanzamt problem",         # Tax office issue — often blocks banking
    "finanzamt issue",
    "finanzamt blocked",
    "steueridentifikationsnummer", # Tax ID — needed for accounts, visa holders struggle
    "steuer id",
    "anmeldung problem",         # Registration issue — no address = no account
    "anmeldung refused",
    "aufenthaltstitel bank",     # Residence permit + bank combo pain
    "niederlassungserlaubnis bank",
    "girokonto für ausländer",   # Current account for foreigners
    "konto für ausländer",
    "ausländerbehörde problem",  # Foreigners authority issue
    "bonitätsprüfung failed",
    "schufa-score",
    "schufa score niedrig",      # Low Schufa score

    # --- Competitor Mentions (HIGHEST CONVERTING — see NOTE below) ---
    # When someone says "N26 wouldn't let me" they are ACTIVELY shopping alternatives.
    # These trigger the `competitor_mentioned` flag and get priority Discord routing.
    "n26 problem", "n26 issue", "n26 doesn't work", "n26 not available",
    "revolut problem", "revolut issue", "revolut not working",
    "wise problem", "wise issue", "wise rejected",
    "commerzbank refused", "commerzbank rejected", "commerzbank problem",
    "sparkasse refused", "sparkasse rejected", "sparkasse problem",
    "deutsche bank refused", "deutsche bank rejected",
    "ing refused", "dkb refused", "comdirect refused",

    # --- Desperation Language ---
    "tried everything", "nobody helps", "impossible in germany",
    "so frustrated", "desperate", "last resort", "please someone",
    "no one will help", "giving up", "can't survive",
    "what do i do", "help please", "urgent help",
]

# =============================================================================
# 🔬 TIER 2 — WARM TRIGGERS
# Confusion, curiosity, research phase. Needs 2+ hits OR 1 hit + question mark.
# =============================================================================

YT_TIER2_TRIGGERS = [
    # --- General Schufa Confusion ---
    "schufa", "credit score", "bonitätsprüfung", "schufa check", "schufa free",
    "no credit history", "credit history germany", "build credit", "kredit",

    # --- Banking Research Phase ---
    "no bank account", "can't open", "n26", "commerzbank", "sparkasse",
    "girokonto", "wise", "revolut", "bunq", "vivid", "trade republic",
    "online bank germany", "digital bank germany",

    # --- Housing Research ---
    "wohnung", "mietschulden", "schufa apartment", "wbs", "mietkaution",
    "rental deposit germany", "apartment hunting germany",

    # --- Newcomer Questions ---
    "just moved", "first month", "just arrived", "new to germany",
    "how do i", "where can i", "any advice", "confused about",
    "help me", "what should i", "does anyone know", "please help",
    "as an expat", "as a foreigner", "as a non-german",

    # --- 🆕 German Admin Terms Expats Google ---
    "aufenthaltserlaubnis", "niederlassungserlaubnis", "blaue karte",
    "blue card germany", "work permit germany", "anmeldung",
    "einwohnermeldeamt", "abmeldung", "visa bank requirement",
    "blocked account germany", "sperrkonto", "freistellungsauftrag",
    "kirchensteuer opt out", "rundfunkbeitrag",

    # --- Financial Research ---
    "loan germany expat", "personal loan germany", "ratenkredit",
    "dispokredit", "overdraft germany", "kredit ohne schufa",
    "schufafreier kredit", "schweizer kredit",
    "p-konto beantragen", "basiskonto beantragen",
    "schufa selbstauskunft", "schufa kostenlos",

    # --- Health / Insurance (financial pain gateway) ---
    "krankenkasse foreigner", "health insurance germany expat",
    "techniker krankenkasse", "aok foreigner", "private vs public insurance",
]

# =============================================================================
# 🎯 COMPETITOR BRAND LIST — Flags highest-intent leads
# When someone names a competitor AND describes rejection, they are
# actively in the market. Conversion rate on these is 3-5× average.
# =============================================================================

COMPETITOR_BRANDS = [
    "n26", "revolut", "wise", "monese", "bunq", "vivid",
    "commerzbank", "sparkasse", "deutsche bank", "ing", "dkb",
    "comdirect", "postbank", "hypovereinsbank", "targobank",
    "fintiba", "expatrio", "coracle", "mawista",
]

# =============================================================================
# KEYWORD → CATEGORY MAPPING (for n8n routing and Discord channel separation)
# =============================================================================

KEYWORD_CATEGORIES = {
    "bank":      ["bank rejected", "account denied", "n26", "commerzbank", "sparkasse",
                  "girokonto", "no bank account", "can't open", "blocked account",
                  "fintiba", "expatrio", "wise", "revolut", "basiskonto", "p-konto",
                  "konto für ausländer"],
    "schufa":    ["schufa", "credit score", "bonitätsprüfung", "schufa check",
                  "schufa free", "negative schufa", "keine schufa", "ohne schufa",
                  "schufa score", "schufa eintrag", "credit history germany",
                  "schufa-auskunft", "schufa löschen"],
    "apartment": ["apartment rejected", "can't rent", "landlord refused",
                  "rental rejected", "wohnung", "mietschulden", "schufa apartment",
                  "mietkaution", "wbs"],
    "loan":      ["loan rejected", "kredit", "kredit abgelehnt", "no credit history",
                  "build credit", "schufafreier kredit", "schweizer kredit",
                  "ratenkredit", "dispokredit"],
    "newcomer":  ["just moved", "first month", "just arrived", "new to germany",
                  "how do i", "any advice", "confused about", "help me",
                  "as an expat", "as a foreigner"],
    "visa":      ["blue card", "aufenthaltserlaubnis", "niederlassungserlaubnis",
                  "work permit", "anmeldung", "visa bank", "ausländerbehörde",
                  "aufenthaltstitel"],
    "tax":       ["finanzamt", "steueridentifikationsnummer", "steuer id",
                  "freistellungsauftrag", "kirchensteuer", "steuernummer"],
}

# =============================================================================
# SCORING THRESHOLDS
# =============================================================================

MIN_GROQ_SCORE              = 45    # Standard gate
MIN_GROQ_SCORE_TIER1        = 35    # Lower gate for Tier 1 (already pre-qualified)
MIN_GROQ_SCORE_COMPETITOR   = 30    # Lowest gate — competitor mention = in-market buyer
MAX_COMMENT_AGE_HOURS       = 96    # Expanded from 72h — catches weekend posts
MIN_COMMENT_LIKES           = 0

# =============================================================================
# DEEP SCAN SETTINGS
# =============================================================================

MAX_COMMENTS_STANDARD       = 75    # Normal videos
MAX_COMMENTS_DEEP           = 200   # Priority/authority videos
DEEP_SCAN_MAX_VIDEO_AGE_DAYS = 7    # Only deep-scan videos < 7 days old
PRIORITY_DENSITY_THRESHOLD  = 0.04  # ≥4% of comments must have Tier1 hits to mark priority
                                    # e.g., 3 hits in 75 comments = 4% → priority

# =============================================================================
# BEHAVIOR SETTINGS
# =============================================================================

MAX_RESULTS_PER_QUERY       = 5
HARVEST_INTERVAL_HOURS      = 3
DISCOVERY_HOUR              = 6
SLEEP_END_HOUR              = 11
SLEEP_START_HOUR            = 1

# Cache files
VIDEO_CACHE_FILE            = "yt_video_cache.json"
HOT_VIDEO_CACHE_FILE        = "yt_hot_videos.json"   # Relevance persistence store
CHANNEL_UPLOADS_CACHE_FILE  = "yt_channel_cache.json" # Channel upload playlist IDs

# API retry
MAX_API_RETRIES             = 3
RETRY_BASE_DELAY_SECS       = 30

# =============================================================================
# LOGGING
# =============================================================================

log = logging.getLogger("YouTubeWorker")

# =============================================================================
# STATE
# =============================================================================

seen_comment_ids: set     = set()
last_discovery_date: date = None
quota_exhausted: bool     = False

# =============================================================================
# YOUTUBE CLIENT
# =============================================================================

def init_youtube():
    client = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    log.info("✅ [YouTube] API client initialised")
    return client

# =============================================================================
# QUOTA-AWARE API CALLER — Exponential backoff on 403/429
# =============================================================================

def api_call_with_retry(api_fn, context: str = ""):
    global quota_exhausted

    for attempt in range(1, MAX_API_RETRIES + 1):
        try:
            return api_fn()

        except HttpError as e:
            status = e.resp.status if hasattr(e, "resp") else 0
            reason = str(e)

            if status == 403 or "quotaExceeded" in reason or "dailyLimitExceeded" in reason:
                log.critical("🚫 [YouTube] QUOTA EXHAUSTED — halting all API calls until midnight")
                quota_exhausted = True
                return None

            elif status == 429:
                delay = RETRY_BASE_DELAY_SECS * (2 ** (attempt - 1))
                log.warning(f"  ⚠  [{context}] Rate limited — retry in {delay}s ({attempt}/{MAX_API_RETRIES})")
                time.sleep(delay)

            elif "commentsDisabled" in reason:
                log.info(f"  ⏭  [{context}] Comments disabled")
                return None

            elif "videoNotFound" in reason or status == 404:
                log.info(f"  ⏭  [{context}] Not found")
                return None

            else:
                log.error(f"  ✖  [{context}] API error attempt {attempt}: {e}")
                if attempt == MAX_API_RETRIES:
                    return None
                time.sleep(RETRY_BASE_DELAY_SECS)

        except Exception as e:
            log.error(f"  ✖  [{context}] Unexpected: {e}")
            return None

    return None

# =============================================================================
# VIDEO CACHE — Standard discovery cache
# Schema: {date, video_ids: [{id, source, channel_name, published_at}]}
# =============================================================================

def save_video_cache(video_entries: list):
    data = {
        "date":         date.today().isoformat(),
        "video_entries": video_entries,
    }
    with open(VIDEO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    log.info(f"  💾 Video cache saved — {len(video_entries)} entries")

def load_video_cache() -> list:
    if not os.path.exists(VIDEO_CACHE_FILE):
        return []
    try:
        with open(VIDEO_CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("date") == date.today().isoformat():
            entries = data.get("video_entries", [])
            log.info(f"  📂 Loaded {len(entries)} video entries from today's cache")
            return entries
        log.info("  📂 Video cache stale — fresh discovery needed")
        return []
    except Exception as e:
        log.warning(f"  ⚠  Video cache read failed: {e}")
        return []

# =============================================================================
# HOT VIDEO CACHE — Relevance Persistence Store
# Tracks per-video metrics across harvest cycles.
# Schema: {video_id: {tier1_density, harvest_count, is_priority, published_at, source}}
# =============================================================================

def load_hot_cache() -> dict:
    if not os.path.exists(HOT_VIDEO_CACHE_FILE):
        return {}
    try:
        with open(HOT_VIDEO_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_hot_cache(hot_cache: dict):
    with open(HOT_VIDEO_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(hot_cache, f, indent=2)

def update_hot_cache(video_id: str, tier1_hits: int, comments_scanned: int,
                     published_at: str, source: str, channel_name: str = ""):
    """
    Updates the hot video cache after each harvest.
    Calculates tier1_density and sets is_priority flag if threshold is met.
    """
    hot_cache = load_hot_cache()

    density = tier1_hits / max(comments_scanned, 1)
    existing = hot_cache.get(video_id, {})

    # Weighted rolling average of density across harvests
    prev_density    = existing.get("tier1_density", 0)
    harvest_count   = existing.get("harvest_count", 0) + 1
    rolling_density = (prev_density * (harvest_count - 1) + density) / harvest_count

    is_priority = rolling_density >= PRIORITY_DENSITY_THRESHOLD

    hot_cache[video_id] = {
        "tier1_density":    round(rolling_density, 4),
        "harvest_count":    harvest_count,
        "is_priority":      is_priority,
        "published_at":     published_at,
        "source":           source,
        "channel_name":     channel_name,
        "last_harvested":   datetime.utcnow().isoformat() + "Z",
    }

    save_hot_cache(hot_cache)
    return is_priority, round(rolling_density, 4)

def get_priority_video_ids() -> list:
    """Returns list of video_ids currently marked as priority."""
    hot_cache = load_hot_cache()
    return [vid_id for vid_id, meta in hot_cache.items() if meta.get("is_priority")]

# =============================================================================
# CHANNEL UPLOADS CACHE — Stores upload playlist IDs (avoids repeated API calls)
# =============================================================================

def load_channel_cache() -> dict:
    if not os.path.exists(CHANNEL_UPLOADS_CACHE_FILE):
        return {}
    try:
        with open(CHANNEL_UPLOADS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_channel_cache(channel_cache: dict):
    with open(CHANNEL_UPLOADS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(channel_cache, f, indent=2)

# =============================================================================
# CHANNEL RADAR — Handle resolution + latest video fetch
# =============================================================================

def resolve_channel_id(youtube, channel: dict) -> str | None:
    """
    Resolves a channel entry to a confirmed channel ID.

    Accepts two formats:
      {"handle": "@SimpleGermany"}  → calls channels.list(forHandle=...) — 1 unit
      {"id": "UCxxxxxxxx"}          → returns directly, zero API cost

    Result is permanently cached in yt_channel_cache.json.
    On all subsequent runs: zero API calls, reads from cache.
    """
    channel_cache = load_channel_cache()
    channel_name  = channel.get("name", "unknown")

    # --- Direct ID provided — verify it's not a placeholder ---
    if "id" in channel and not channel["id"].startswith("PLACEHOLDER"):
        channel_id = channel["id"]
        # Cache it for consistency (so cache always has full picture)
        if channel_id not in channel_cache:
            channel_cache[channel_id] = {"channel_id": channel_id, "name": channel_name}
            save_channel_cache(channel_cache)
        return channel_id

    # --- Handle provided — check cache first ---
    handle = channel.get("handle", "")
    if not handle:
        log.warning(f"  ⚠  [{channel_name}] No 'id' or 'handle' field — skipping")
        return None

    cache_key = f"handle:{handle}"
    if cache_key in channel_cache:
        cached_id = channel_cache[cache_key].get("channel_id")
        log.info(f"  📺 [{channel_name}] Resolved from cache: {cached_id}")
        return cached_id

    # --- Resolve handle via API (cost: 1 unit, runs only once ever) ---
    log.info(f"  🔍 [{channel_name}] Resolving handle {handle} → channel ID...")
    result = api_call_with_retry(
        lambda h=handle: youtube.channels().list(
            part="id,snippet",
            forHandle=h.lstrip("@"),   # API accepts handle without @ prefix
        ).execute(),
        context=f"resolve_handle:{handle}"
    )

    if not result or not result.get("items"):
        log.warning(f"  ⚠  [{channel_name}] Handle {handle} not found — check spelling")
        return None

    channel_id   = result["items"][0]["id"]
    display_name = result["items"][0]["snippet"]["title"]

    channel_cache[cache_key] = {
        "channel_id":   channel_id,
        "name":         display_name,
        "handle":       handle,
        "resolved_at":  datetime.utcnow().isoformat() + "Z",
    }
    save_channel_cache(channel_cache)
    log.info(f"  ✅ [{channel_name}] Resolved: {handle} → {channel_id} ({display_name})")
    return channel_id


def get_channel_upload_playlist(youtube, channel_id: str, channel_name: str = "") -> str | None:
    """
    Fetches the 'uploads' playlist ID for a resolved channel ID.
    Cost: 1 unit on first call. Cached permanently.
    """
    channel_cache = load_channel_cache()
    playlist_key  = f"playlist:{channel_id}"

    if playlist_key in channel_cache:
        return channel_cache[playlist_key]["uploads_playlist_id"]

    result = api_call_with_retry(
        lambda: youtube.channels().list(
            part="contentDetails",
            id=channel_id,
        ).execute(),
        context=f"uploads_playlist:{channel_id[:20]}"
    )

    if not result or not result.get("items"):
        log.warning(f"  ⚠  [{channel_name}] Could not fetch uploads playlist for {channel_id}")
        return None

    uploads_playlist_id = result["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    channel_cache[playlist_key] = {"uploads_playlist_id": uploads_playlist_id}
    save_channel_cache(channel_cache)
    log.info(f"  📺 [{channel_name}] Uploads playlist cached: {uploads_playlist_id}")
    return uploads_playlist_id


def fetch_channel_latest_videos(youtube, channel: dict) -> list:
    """
    Fetches the latest N videos from a monitored channel.
    Accepts both handle-based and ID-based channel entries.
    Cost: 1–2 units total (resolve + playlist fetch, both cached after first run).

    Returns list of video entry dicts compatible with video cache format.
    """
    channel_name = channel.get("name", "unknown")

    # Step 1: Resolve to confirmed channel ID
    channel_id = resolve_channel_id(youtube, channel)
    if not channel_id or quota_exhausted:
        return []

    # Step 2: Get uploads playlist ID
    uploads_playlist_id = get_channel_upload_playlist(youtube, channel_id, channel_name)
    if not uploads_playlist_id or quota_exhausted:
        return []

    # Step 3: Fetch latest videos
    result = api_call_with_retry(
        lambda: youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=CHANNEL_VIDEOS_PER_FETCH,
        ).execute(),
        context=f"channel_videos:{channel_name[:20]}"
    )

    if not result:
        return []

    video_entries = []
    for item in result.get("items", []):
        vid_id       = item["contentDetails"].get("videoId", "")
        published_at = item["snippet"].get("publishedAt", "")
        title        = item["snippet"].get("title", "")

        if not vid_id:
            continue

        video_entries.append({
            "id":           vid_id,
            "source":       "channel",
            "channel_name": channel_name,
            "channel_id":   channel_id,
            "published_at": published_at,
            "title":        title,
        })

    log.info(f"  📺 [{channel_name}] {len(video_entries)} latest video(s) fetched")
    return video_entries

# =============================================================================
# TWO-TIER RELEVANCE ENGINE + COMPETITOR DETECTION
# =============================================================================

def classify_comment(comment_text: str) -> tuple[bool, list[str], str, bool, bool]:
    """
    Full comment classification pipeline. Zero API cost.

    Returns:
        should_score (bool)
        all_matched (list[str])
        intent_tier (str):         "CRITICAL" | "WARM" | "NOISE"
        is_question (bool)
        competitor_mentioned (bool)
    """
    text_lower  = comment_text.lower()
    tier1_hits  = [kw for kw in YT_TIER1_TRIGGERS if kw in text_lower]
    tier2_hits  = [kw for kw in YT_TIER2_TRIGGERS if kw in text_lower]
    all_matched = list(dict.fromkeys(tier1_hits + tier2_hits))

    is_question          = any(c in text_lower for c in ["?", "how ", "where ", "what ", "why ", "can i ", "should i "])
    competitor_mentioned = any(brand in text_lower for brand in COMPETITOR_BRANDS)

    # Intent classification
    if tier1_hits or (competitor_mentioned and tier2_hits):
        intent_tier  = "CRITICAL"
        should_score = True
    elif len(tier2_hits) >= 2:
        intent_tier  = "WARM"
        should_score = True
    elif len(tier2_hits) == 1 and is_question:
        intent_tier  = "WARM"
        should_score = True
    elif competitor_mentioned and is_question:
        # Competitor + question = in-market buyer even without explicit keywords
        intent_tier  = "WARM"
        should_score = True
    else:
        intent_tier  = "NOISE"
        should_score = False

    return should_score, all_matched, intent_tier, is_question, competitor_mentioned


def get_keyword_category(matched_keywords: list) -> str:
    category_counts = {}
    for category, kw_list in KEYWORD_CATEGORIES.items():
        hits = sum(1 for kw in matched_keywords if any(c in kw for c in kw_list))
        if hits > 0:
            category_counts[category] = hits
    return max(category_counts, key=category_counts.get) if category_counts else "general"


def get_comment_age_hours(published_at: str) -> float:
    try:
        dt  = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() / 3600
    except Exception:
        return 999.0


def get_video_age_days(published_at: str) -> float:
    try:
        dt  = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() / 86400
    except Exception:
        return 999.0

# =============================================================================
# n8n DELIVERY
# =============================================================================

def send_to_n8n(payload: dict) -> bool:
    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=15,
            headers={"Content-Type": "application/json"},
        )
        if response.status_code in (200, 204):
            competitor_tag = "🎯COMPETITOR" if payload.get("competitor_mentioned") else ""
            priority_tag   = "⭐PRIORITY"   if payload.get("is_priority_video")   else ""
            log.info(
                f"   ↗  Sent → n8n [{response.status_code}] "
                f"{competitor_tag}{priority_tag} "
                f"[{payload['intent_tier']}] "
                f"Score:{payload['groq_score']}/100 "
                f"Age:{payload['comment_age_hours']:.1f}h | "
                f"{payload['comment_text'][:40]}"
            )
            return True
        else:
            log.warning(f"   ⚠  n8n {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        log.error(f"   ✖  Delivery failed: {e}")
        return False

# =============================================================================
# DISCOVERY PHASE — Path A: Keyword Search
# =============================================================================

def run_keyword_discovery(youtube) -> list:
    """
    Searches YouTube by keyword queries.
    Cost: 100 units per query.
    Returns list of video entry dicts.
    """
    log.info(f"  🔍 Keyword Discovery — {len(YT_SEARCH_QUERIES)} queries × 100 units")
    video_entries     = []
    seen_in_discovery = set()

    for query in YT_SEARCH_QUERIES:
        result = api_call_with_retry(
            lambda q=query: youtube.search().list(
                q=q,
                part="id,snippet",
                type="video",
                maxResults=MAX_RESULTS_PER_QUERY,
                order="relevance",
                relevanceLanguage="en",
                regionCode="DE",
            ).execute(),
            context=f"search:{query[:25]}"
        )

        if quota_exhausted:
            break
        if not result:
            continue

        found = 0
        for item in result.get("items", []):
            vid_id = item["id"].get("videoId", "")
            if not vid_id or vid_id in seen_in_discovery:
                continue
            seen_in_discovery.add(vid_id)
            video_entries.append({
                "id":           vid_id,
                "source":       "search",
                "channel_name": item["snippet"].get("channelTitle", ""),
                "channel_id":   item["snippet"].get("channelId", ""),
                "published_at": item["snippet"].get("publishedAt", ""),
                "title":        item["snippet"].get("title", ""),
            })
            found += 1

        log.info(f"  ✔  \"{query}\" → {found} video(s)")
        time.sleep(random.uniform(2, 4))

    return video_entries

# =============================================================================
# DISCOVERY PHASE — Path B: Channel Radar
# =============================================================================

def run_channel_discovery(youtube) -> list:
    """
    Fetches latest videos from all MONITORED_CHANNELS.
    Cost: ~1 unit per channel (playlistItems.list — 100× cheaper than search).
    Returns list of video entry dicts.
    """
    log.info(f"  📡 Channel Radar — {len(MONITORED_CHANNELS)} channels × ~1 unit each")
    video_entries     = []
    seen_in_discovery = set()

    for channel in MONITORED_CHANNELS:
        if quota_exhausted:
            break

        entries = fetch_channel_latest_videos(youtube, channel)
        for entry in entries:
            if entry["id"] not in seen_in_discovery:
                seen_in_discovery.add(entry["id"])
                video_entries.append(entry)

        time.sleep(random.uniform(1, 3))

    return video_entries

# =============================================================================
# DISCOVERY COORDINATOR — Merges both paths, deduplicates, saves cache
# =============================================================================

def run_discovery(youtube) -> list:
    global quota_exhausted

    if quota_exhausted:
        log.warning("  ⚠  Quota exhausted — loading cache")
        return load_video_cache()

    log.info("=" * 65)
    log.info(f"🔭 DISCOVERY RUN | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"   Path A: Keyword search × {len(YT_SEARCH_QUERIES)} queries (~700 units)")
    log.info(f"   Path B: Channel radar × {len(MONITORED_CHANNELS)} channels (~{len(MONITORED_CHANNELS)} units)")
    log.info("=" * 65)

    # Path A: Keyword search
    keyword_entries = run_keyword_discovery(youtube)
    log.info(f"  📊 Path A complete — {len(keyword_entries)} videos from keyword search")

    # Path B: Channel radar (always runs if quota allows — cheap)
    channel_entries = []
    if not quota_exhausted:
        channel_entries = run_channel_discovery(youtube)
        log.info(f"  📊 Path B complete — {len(channel_entries)} videos from channel radar")

    # Merge and deduplicate by video ID
    all_entries    = keyword_entries + channel_entries
    seen_ids       = set()
    merged_entries = []
    for entry in all_entries:
        if entry["id"] not in seen_ids:
            seen_ids.add(entry["id"])
            merged_entries.append(entry)

    # Inject previously identified priority videos (preserve hot targets across days)
    priority_ids     = get_priority_video_ids()
    hot_cache        = load_hot_cache()
    priority_entries = []
    existing_ids     = {e["id"] for e in merged_entries}

    for vid_id in priority_ids:
        if vid_id not in existing_ids:
            meta = hot_cache.get(vid_id, {})
            published_at = meta.get("published_at", "")
            age_days     = get_video_age_days(published_at)
            if age_days <= DEEP_SCAN_MAX_VIDEO_AGE_DAYS * 2:  # Keep priority videos a bit longer
                priority_entries.append({
                    "id":           vid_id,
                    "source":       meta.get("source", "priority_carry"),
                    "channel_name": meta.get("channel_name", ""),
                    "published_at": published_at,
                    "title":        "",
                })

    if priority_entries:
        log.info(f"  ⭐ Carrying forward {len(priority_entries)} priority video(s) from hot cache")
        merged_entries = priority_entries + merged_entries  # Priority first

    save_video_cache(merged_entries)
    log.info(f"  📊 Discovery complete — {len(merged_entries)} unique video(s) cached total")
    return merged_entries

# =============================================================================
# HARVEST PHASE — Single video, smart depth selection
# =============================================================================

def harvest_video(youtube, video_entry: dict, hot_cache: dict) -> tuple[int, int, int]:
    """
    Harvests comments from a single video.
    Automatically selects deep (200) or standard (75) comment depth.

    Returns:
        sent (int):     Comments forwarded to n8n
        scanned (int):  Total comments processed
        tier1_hits (int): Number of Tier 1 keyword matches (for density calculation)
    """
    video_id     = video_entry["id"]
    published_at = video_entry.get("published_at", "")
    source       = video_entry.get("source", "search")
    channel_name = video_entry.get("channel_name", "")
    video_url    = f"https://www.youtube.com/watch?v={video_id}"

    # --- Determine scan depth ---
    video_age_days   = get_video_age_days(published_at)
    video_meta       = hot_cache.get(video_id, {})
    already_priority = video_meta.get("is_priority", False)
    is_channel_video = source == "channel"

    # Deep scan criteria:
    # 1. Video < 7 days old (fresh content, high comment activity)
    # 2. Already marked priority from previous harvest
    # 3. Comes directly from a monitored channel (authority signal)
    use_deep_scan = (
        video_age_days <= DEEP_SCAN_MAX_VIDEO_AGE_DAYS
        or already_priority
        or is_channel_video
    )

    comment_limit = MAX_COMMENTS_DEEP if use_deep_scan else MAX_COMMENTS_STANDARD
    scan_label    = "🔬 DEEP" if use_deep_scan else "📄 STANDARD"

    log.info(f"  📹 [{scan_label}] {video_url} | Source: {source} | Age: {video_age_days:.1f}d")

    result = api_call_with_retry(
        lambda vid=video_id: youtube.commentThreads().list(
            part="snippet",
            videoId=vid,
            maxResults=min(comment_limit, 100),  # API max per page is 100
            order="relevance",
            textFormat="plainText",
        ).execute(),
        context=f"harvest:{video_id}"
    )

    if not result:
        return 0, 0, 0

    sent      = 0
    scanned   = 0
    tier1_hits_count = 0
    items     = result.get("items", [])

    # If deep scan and > 100 comments needed, fetch second page
    if use_deep_scan and comment_limit > 100 and result.get("nextPageToken") and not quota_exhausted:
        next_token = result.get("nextPageToken")
        page2 = api_call_with_retry(
            lambda vid=video_id, tok=next_token: youtube.commentThreads().list(
                part="snippet",
                videoId=vid,
                maxResults=min(comment_limit - 100, 100),
                order="relevance",
                textFormat="plainText",
                pageToken=tok,
            ).execute(),
            context=f"harvest_p2:{video_id}"
        )
        if page2:
            items.extend(page2.get("items", []))

    for item in items:
        snippet      = item["snippet"]["topLevelComment"]["snippet"]
        comment_id   = item["snippet"]["topLevelComment"]["id"]
        comment_text = snippet.get("textDisplay", "").strip()
        author       = snippet.get("authorDisplayName", "[unknown]")
        likes        = snippet.get("likeCount", 0)
        reply_count  = item["snippet"].get("totalReplyCount", 0)
        pub_at       = snippet.get("publishedAt", "")

        scanned += 1

        if comment_id in seen_comment_ids:
            continue

        # --- Age filter ---
        age_hours = get_comment_age_hours(pub_at)
        if age_hours > MAX_COMMENT_AGE_HOURS:
            seen_comment_ids.add(comment_id)
            continue

        if likes < MIN_COMMENT_LIKES:
            seen_comment_ids.add(comment_id)
            continue

        # --- Stage 1: Two-tier classification ---
        should_score, matched_kws, intent_tier, is_question, competitor_mentioned = classify_comment(comment_text)

        # Track Tier 1 density regardless of should_score
        tier1_in_comment = sum(1 for kw in YT_TIER1_TRIGGERS if kw in comment_text.lower())
        tier1_hits_count += min(tier1_in_comment, 1)  # Count videos not keywords

        if not should_score:
            seen_comment_ids.add(comment_id)
            continue

        # --- Stage 2: Groq scoring with tiered gates ---
        groq_score = score_lead(
            content=comment_text,
            matched_keywords=matched_kws,
            source="youtube"
        )

        # Select appropriate gate
        if competitor_mentioned:
            score_gate = MIN_GROQ_SCORE_COMPETITOR
        elif intent_tier == "CRITICAL":
            score_gate = MIN_GROQ_SCORE_TIER1
        else:
            score_gate = MIN_GROQ_SCORE

        if groq_score < score_gate:
            log.info(f"   🔕 [{intent_tier}] Score {groq_score} < gate {score_gate} — skipped")
            seen_comment_ids.add(comment_id)
            continue

        # --- Enrichment ---
        primary_category  = get_keyword_category(matched_kws)
        reply_opportunity = is_question and reply_count == 0
        deep_comment_link = f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"

        # --- Payload ---
        payload = {
            # Routing
            "source":               "youtube",

            # Identity
            "user":                 author,
            "author_channel":       snippet.get("authorChannelUrl", ""),

            # IDs
            "comment_id":           comment_id,
            "video_id":             video_id,

            # Content
            "comment_text":         comment_text[:2500],

            # Links
            "link":                 deep_comment_link,     # ✅ Deep comment link
            "video_url":            video_url,

            # Scoring & Intent
            "groq_score":           groq_score,
            "intent_tier":          intent_tier,           # CRITICAL | WARM
            "score_gate_used":      score_gate,

            # Competitor Intelligence (HIGHEST CONVERTING)
            "competitor_mentioned": competitor_mentioned,  # ✅ In-market buyer flag
            "competitors_found":    [b for b in COMPETITOR_BRANDS
                                     if b in comment_text.lower()],

            # Keyword Intelligence
            "matched_keywords":     matched_kws,
            "keyword_count":        len(matched_kws),
            "keyword_category":     primary_category,

            # Video Metadata
            "video_source":         source,                # "search" | "channel"
            "channel_name":         channel_name,
            "is_priority_video":    already_priority,      # ✅ Relevance persistence flag
            "video_age_days":       round(video_age_days, 1),
            "scan_depth":           comment_limit,         # How deep we scanned

            # Freshness
            "is_question":          is_question,
            "reply_opportunity":    reply_opportunity,
            "comment_age_hours":    round(age_hours, 1),
            "reply_count":          reply_count,
            "likes":                likes,

            # Timestamps
            "published_at":         pub_at,
            "scraped_at":           datetime.utcnow().isoformat() + "Z",
        }

        success = send_to_n8n(payload)
        if success:
            seen_comment_ids.add(comment_id)
            sent += 1

        time.sleep(random.uniform(0.8, 2.5))

    return sent, scanned, tier1_hits_count

# =============================================================================
# HARVEST COORDINATOR — Runs all videos, updates hot cache
# =============================================================================

def run_harvest(youtube, video_entries: list) -> int:
    global quota_exhausted

    if not video_entries:
        log.warning("  ⚠  No videos to harvest")
        return 0
    if quota_exhausted:
        log.warning("  ⚠  Quota exhausted — harvest skipped")
        return 0

    hot_cache     = load_hot_cache()
    priority_ids  = {vid_id for vid_id, m in hot_cache.items() if m.get("is_priority")}

    # Sort: priority videos first, then by age (freshest first)
    def sort_key(entry):
        is_priority = entry["id"] in priority_ids
        age_days    = get_video_age_days(entry.get("published_at", ""))
        return (0 if is_priority else 1, age_days)

    sorted_entries = sorted(video_entries, key=sort_key)

    log.info("=" * 65)
    log.info(f"🌾 HARVEST RUN | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"   Videos total   : {len(sorted_entries)}")
    log.info(f"   Priority videos: {len(priority_ids)}")
    log.info(f"   Channel videos : {sum(1 for e in sorted_entries if e.get('source') == 'channel')}")
    log.info("=" * 65)

    total_sent    = 0
    total_scanned = 0
    newly_priority = 0

    for entry in sorted_entries:
        if quota_exhausted:
            log.warning("  ⚠  Quota exhausted mid-harvest — stopping")
            break

        sent, scanned, tier1_hits = harvest_video(youtube, entry, hot_cache)
        total_sent    += sent
        total_scanned += scanned

        # Update hot cache with density metrics
        is_now_priority, density = update_hot_cache(
            video_id     = entry["id"],
            tier1_hits   = tier1_hits,
            comments_scanned = max(scanned, 1),
            published_at = entry.get("published_at", ""),
            source       = entry.get("source", "search"),
            channel_name = entry.get("channel_name", ""),
        )

        if is_now_priority and entry["id"] not in priority_ids:
            newly_priority += 1
            log.info(f"  ⭐ NEW PRIORITY: {entry['id']} | density={density:.3f}")

        time.sleep(random.uniform(3, 8))

    log.info(
        f"  📊 Harvest complete — "
        f"Videos:{len(sorted_entries)} | "
        f"Scanned:{total_scanned} | "
        f"Sent:{total_sent} | "
        f"New priority:{newly_priority}"
    )
    return total_sent

# =============================================================================
# SCHEDULE HELPERS
# =============================================================================

def is_sleep_window() -> bool:
    return SLEEP_START_HOUR <= datetime.now().hour < SLEEP_END_HOUR

def wait_until_active():
    now    = datetime.now()
    target = now.replace(hour=SLEEP_END_HOUR, minute=0, second=0, microsecond=0)
    delta  = (target - now).total_seconds()
    if delta <= 0:
        return
    h, m = int(delta // 3600), int((delta % 3600) // 60)
    log.info(f"🌙 [YouTube] SLEEP — {h}h {m}m until 11:00")
    time.sleep(delta)
    log.info("☀️  [YouTube] 11:00 — YouTubeWorker live")

def is_discovery_due() -> bool:
    global last_discovery_date
    today = date.today()
    if last_discovery_date == today:
        return False
    cached = load_video_cache()
    if cached:
        last_discovery_date = today
        return False
    return True

def wait_for_quota_reset():
    global quota_exhausted
    now      = datetime.now()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
    secs     = (midnight - now).total_seconds()
    log.info(f"🚫 [YouTube] Quota exhausted. Sleeping {secs/3600:.1f}h until midnight.")
    time.sleep(secs)
    quota_exhausted = False
    log.info("✅ [YouTube] Quota reset — resuming")

def harvest_sleep():
    jitter_min = random.uniform(-10, 10)
    total_secs = (HARVEST_INTERVAL_HOURS * 3600) + (jitter_min * 60)
    log.info(f"  ⏳ Next harvest in {total_secs/60:.0f} min")
    time.sleep(total_secs)

# =============================================================================
# MAIN LOOP
# =============================================================================

def main():
    global last_discovery_date, quota_exhausted

    log.info("=" * 65)
    log.info("🚀 [YouTube] YouTubeWorker 1.3 — Deep Search & Channel Authority (Final)")
    log.info(f"   Tier 1 triggers  : {len(YT_TIER1_TRIGGERS)} CRITICAL phrases")
    log.info(f"   Tier 2 triggers  : {len(YT_TIER2_TRIGGERS)} WARM phrases")
    log.info(f"   Competitor brands: {len(COMPETITOR_BRANDS)}")
    log.info(f"   Monitored channels: {len(MONITORED_CHANNELS)} (handle auto-resolution enabled)")
    for ch in MONITORED_CHANNELS:
        identifier = ch.get('handle', ch.get('id', 'unknown'))
        log.info(f"     • {ch['name']} ({identifier})")
    log.info(f"   Scan depth       : {MAX_COMMENTS_STANDARD} standard / {MAX_COMMENTS_DEEP} deep")
    log.info(f"   Deep scan gate   : videos < {DEEP_SCAN_MAX_VIDEO_AGE_DAYS} days old")
    log.info(f"   Priority density : ≥{PRIORITY_DENSITY_THRESHOLD*100:.0f}% Tier1 hits → priority")
    log.info(f"   Estimated budget : ~895 units/day (91% headroom)")
    log.info("=" * 65)

    youtube       = init_youtube()
    video_entries = []

    while True:
        if is_sleep_window():
            wait_until_active()

        if quota_exhausted:
            wait_for_quota_reset()
            continue

        if is_discovery_due():
            video_entries       = run_discovery(youtube)
            last_discovery_date = date.today()
        elif not video_entries:
            video_entries = load_video_cache()
            if not video_entries:
                log.warning("  ⚠  No cached videos — waiting 30 min")
                time.sleep(1800)
                continue

        run_harvest(youtube, video_entries)

        next_harvest_dt = datetime.fromtimestamp(
            datetime.now().timestamp() + HARVEST_INTERVAL_HOURS * 3600
        )
        if next_harvest_dt.hour >= SLEEP_START_HOUR or next_harvest_dt.hour < SLEEP_END_HOUR:
            log.info("  🌙 Next harvest in silent window — sleeping now.")
            wait_until_active()
        else:
            harvest_sleep()

# =============================================================================
# STANDALONE ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    try:
        from dotenv import load_dotenv
        load_dotenv()
        YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", YOUTUBE_API_KEY)
        N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", N8N_WEBHOOK_URL)
        log.info("  ✅ .env loaded")
    except ImportError:
        log.warning("  ⚠  python-dotenv not installed")

    try:
        main()
    except KeyboardInterrupt:
        log.info("🔴 [YouTube] Stopped.")
    except Exception as e:
        log.critical(f"💥 [YouTube] Fatal: {e}", exc_info=True)
        raise