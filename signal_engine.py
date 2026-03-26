"""
signal_engine.py — ExpatScore Signal Intelligence Engine
Pulls Reddit posts from your Node.js Lead Hunter, scores them via Groq API,
and stores structured intelligence in a local SQLite database.

Usage:
    python signal_engine.py              # Score new posts, show top signals
    python signal_engine.py --top 20     # Show top 20 signals
    python signal_engine.py --reset      # Clear DB and rescore everything
"""

import sqlite3
import requests
import json
import argparse
import sys
import time
import os
from datetime import datetime
from groq import Groq

# ─── CONFIG ──────────────────────────────────────────────────────────────────

LEAD_HUNTER_URL = "http://localhost:3000/hunt/json"
DB_PATH         = "expatscore_signals.db"
GROQ_MODEL      = "llama-3.3-70b-versatile"
MAX_TOKENS      = 512
SCORE_DELAY_SEC = 0.5   # delay between API calls to stay within rate limits

# ─── DATABASE SETUP ──────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id                TEXT PRIMARY KEY,
    raw_title         TEXT,
    raw_body          TEXT,
    source            TEXT DEFAULT 'reddit',
    subreddit         TEXT,
    url               TEXT,
    upvotes           INTEGER DEFAULT 0,

    -- Claude-assigned scores (0-100)
    seo_score         INTEGER,
    viral_score       INTEGER,
    partner_fit_score INTEGER,
    pain_intensity    INTEGER,

    -- Claude-generated content seeds
    keyword_hint      TEXT,
    video_hook        TEXT,
    partner_category  TEXT,
    content_angle     TEXT,

    scored_at         TEXT,
    created_at        TEXT DEFAULT (datetime('now'))
);
"""

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    conn.commit()
    return conn


# ─── FETCH FROM LEAD HUNTER ──────────────────────────────────────────────────

def fetch_posts(url: str) -> list[dict]:
    """Pull raw posts from your Node.js Lead Hunter."""
    print(f"\n[1/3] Fetching posts from Lead Hunter: {url}")
    try:
        headers = {"Accept": "application/json"}
        r = requests.get(url, timeout=10, headers=headers)
        r.raise_for_status()

        content_type = r.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            print(f"      ERROR: Server returned {content_type}, not JSON.")
            print("      Make sure your Node.js server returns raw JSON when called by Python.")
            sys.exit(1)

        posts = r.json()

        # Normalise: handle both array and {posts: [...]} shapes
        if isinstance(posts, dict):
            posts = posts.get("posts") or posts.get("data") or posts.get("results") or []

        print(f"      Fetched {len(posts)} posts.")
        return posts

    except requests.exceptions.ConnectionError:
        print("\n  ERROR: Cannot reach localhost:3000.")
        print("  Make sure your Node.js server is running: node server.js")
        sys.exit(1)
    except Exception as e:
        print(f"\n  ERROR fetching posts: {e}")
        sys.exit(1)


def normalise_post(raw: dict) -> dict:
    """
    Map your Node.js post shape to a standard internal shape.
    Supports typical Reddit JSON fields as well as the structure returned by server.js.
    """
    return {
        "id":        str(raw.get("id") or raw.get("post_id") or raw.get("name") or hash(str(raw))),
        "title":     raw.get("title") or raw.get("post_title") or "",
        "body":      raw.get("body") or raw.get("selftext") or raw.get("content") or raw.get("text") or "",
        "subreddit": raw.get("subreddit") or raw.get("subreddit_name") or "",
        "url":       raw.get("url") or raw.get("permalink") or "",
        "upvotes":   int(raw.get("score") or raw.get("upvotes") or raw.get("ups") or 0),
    }


# ─── GROQ SCORING (replaces Claude) ─────────────────────────────────────────

SCORING_PROMPT = """You are a growth intelligence analyst for ExpatScore.de, a SaaS product that helps expats in Germany navigate SCHUFA, banking, tax, blocked accounts, and bureaucratic rules.

Analyse this Reddit post from an expat community and return ONLY a valid JSON object — no markdown, no explanation, just the raw JSON.

POST TITLE: {title}
POST BODY: {body}
SUBREDDIT: {subreddit}

Score each dimension 0-100 and fill every field:

{{
  "seo_score": <0-100: How well does this map to a high-intent, low-competition Google search query? High = specific question, clear keyword, likely searched often>,
  "viral_score": <0-100: Short-form video potential. High = emotional, relatable, shocking, or story-driven. Would stop a scroll?>,
  "partner_fit_score": <0-100: Could a company (bank, tax advisor, insurance, relocation service) sponsor content around this pain point?>,
  "pain_intensity": <0-100: How urgent and frequent is this problem? High = person is stuck, stressed, or losing money>,
  "keyword_hint": "<best long-tail German expat keyword this maps to, e.g. 'open N26 account without SCHUFA Germany'>",
  "video_hook": "<one punchy TikTok/Reels opening line under 15 words, e.g. 'Germany rejected my bank application 3 times. Here is why.'>",
  "partner_category": "<type of company that solves this, e.g. 'neobank', 'tax advisor', 'relocation service', 'insurance', 'none'>",
  "content_angle": "<suggested article angle in one sentence, e.g. 'Step-by-step guide to building SCHUFA score from zero as a new expat'>"
}}

IMPORTANT INSTRUCTIONS:
- The `keyword_hint` must be a specific long-tail search query that a real expat would type into Google (e.g., "how to get a German bank account without SCHUFA").
- The `content_angle` will become the H1 of the article; make it compelling, SEO‑friendly (50–60 chars), and directly tied to the pain point.
- All scores must be integers between 0 and 100.
- If the post is irrelevant to expat struggles, set all scores low and use `none` for partner_category."""


def score_post(client: Groq, post: dict) -> dict | None:
    """Send one post to Groq and get back a structured score dict."""
    prompt = SCORING_PROMPT.format(
        title     = post["title"],
        body      = (post["body"] or "")[:800],
        subreddit = post["subreddit"],
    )

    try:
        # Use JSON mode to guarantee valid JSON output
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},
        )

        raw = completion.choices[0].message.content.strip()

        # Remove any potential markdown fences (just in case)
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        scores = json.loads(raw)
        return scores

    except json.JSONDecodeError as e:
        print(f"      WARN: Could not parse Groq response for '{post['title'][:50]}': {e}")
        return None
    except Exception as e:
        print(f"      WARN: Groq API error for '{post['title'][:50]}': {e}")
        return None


# ─── MAIN PIPELINE ───────────────────────────────────────────────────────────

def run_pipeline(reset: bool = False):
    # Initialize Groq client (reads GROQ_API_KEY from environment)
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    db     = get_db()

    if reset:
        db.execute("DELETE FROM signals")
        db.commit()
        print("[!] Database cleared for fresh run.")

    # 1. Fetch
    raw_posts = fetch_posts(LEAD_HUNTER_URL)
    posts     = [normalise_post(p) for p in raw_posts]

    # 2. Filter out already-scored posts
    existing = {row["id"] for row in db.execute("SELECT id FROM signals").fetchall()}
    new_posts = [p for p in posts if p["id"] not in existing]
    print(f"\n[2/3] Scoring {len(new_posts)} new posts ({len(posts) - len(new_posts)} already in DB)...")

    if not new_posts:
        print("      Nothing new to score. Run with --reset to re-score everything.")
    else:
        for i, post in enumerate(new_posts, 1):
            title_preview = post["title"][:55] + "..." if len(post["title"]) > 55 else post["title"]
            print(f"      [{i}/{len(new_posts)}] Scoring: {title_preview}")

            scores = score_post(client, post)
            if scores is None:
                continue

            db.execute("""
                INSERT OR REPLACE INTO signals
                  (id, raw_title, raw_body, subreddit, url, upvotes,
                   seo_score, viral_score, partner_fit_score, pain_intensity,
                   keyword_hint, video_hook, partner_category, content_angle, scored_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                post["id"],
                post["title"],
                post["body"],
                post["subreddit"],
                post["url"],
                post["upvotes"],
                scores.get("seo_score"),
                scores.get("viral_score"),
                scores.get("partner_fit_score"),
                scores.get("pain_intensity"),
                scores.get("keyword_hint"),
                scores.get("video_hook"),
                scores.get("partner_category"),
                scores.get("content_angle"),
                datetime.utcnow().isoformat(),
            ))
            db.commit()
            time.sleep(SCORE_DELAY_SEC)   # Respect Groq rate limits

    # 3. Display results
    print_top_signals(db)


# ─── DISPLAY ─────────────────────────────────────────────────────────────────

def print_top_signals(db: sqlite3.Connection, limit: int = 15):
    print(f"\n[3/3] Top Signals in your DB\n")

    sections = [
        ("SEO Targets",        "seo_score",         "keyword_hint",      "content_angle"),
        ("Viral Video Hooks",  "viral_score",       "video_hook",        "keyword_hint"),
        ("Partnership Leads",  "partner_fit_score", "partner_category",  "keyword_hint"),
    ]

    for label, score_col, field1, field2 in sections:
        print(f"  {'─'*60}")
        print(f"  {label} (ranked by {score_col})")
        print(f"  {'─'*60}")

        rows = db.execute(f"""
            SELECT raw_title, {score_col}, {field1}, {field2}
            FROM signals
            WHERE {score_col} IS NOT NULL
            ORDER BY {score_col} DESC
            LIMIT {limit}
        """).fetchall()

        if not rows:
            print("  No data yet.\n")
            continue

        for row in rows:
            title   = (row[0] or "")[:50]
            score   = row[1]
            hint    = row[2] or "—"
            angle   = row[3] or "—"
            bar     = "█" * (score // 10) + "░" * (10 - score // 10)
            print(f"  [{bar}] {score:>3}  {title}")
            print(f"         {hint}")
            print(f"         → {angle}\n")

    total = db.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
    print(f"  Total signals in DB: {total}")
    print(f"  DB file: {DB_PATH}\n")


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ExpatScore Signal Intelligence Engine")
    parser.add_argument("--reset", action="store_true", help="Clear DB and rescore all posts")
    parser.add_argument("--top",   type=int, default=15,  help="Number of top signals to display")
    parser.add_argument("--view",  action="store_true",   help="Just display DB, no new scoring")
    args = parser.parse_args()

    if args.view:
        db = get_db()
        print_top_signals(db, limit=args.top)
    else:
        run_pipeline(reset=args.reset)