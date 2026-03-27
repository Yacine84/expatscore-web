"""
generate_pages.py — ExpatScore Programmatic SEO Page Generator
Reads top signals from expatscore_signals.db, generates full article
content via Groq API, and renders HTML files into /docs via Jinja2.

Usage:
    python generate_pages.py                # Generate top 10 SEO articles
    python generate_pages.py --limit 20     # Generate top 20
    python generate_pages.py --min-score 75 # Only signals with seo_score >= 75
    python generate_pages.py --dry-run      # Preview without writing files
    python generate_pages.py --force        # Regenerate already-built pages
"""

import sqlite3
import json
import argparse
import sys
import time
import re
import os
from datetime import datetime, date
from pathlib import Path

from groq import Groq
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# ─── CONFIG ──────────────────────────────────────────────────────────────────

DB_PATH       = "expatscore_signals.db"
TEMPLATE_DIR  = Path("templates")
OUTPUT_DIR    = Path("docs")
GROQ_MODEL    = "llama-3.3-70b-versatile"
MAX_TOKENS    = 2000
REQUEST_DELAY = 1.0  # seconds between API calls

# ─── DATABASE SETUP ──────────────────────────────────────────────────────────
# Updated schema with intro_paragraph column
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
    created_at        TEXT DEFAULT (datetime('now')),
    intro_paragraph   TEXT      -- added for blog index summary
);
"""

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def fetch_top_signals(db: sqlite3.Connection, limit: int, min_score: int) -> list:
    rows = db.execute("""
        SELECT id, raw_title, raw_body, subreddit, url,
               seo_score, keyword_hint, content_angle, partner_category,
               video_hook
        FROM signals
        WHERE seo_score >= ?
          AND keyword_hint IS NOT NULL
          AND content_angle IS NOT NULL
        ORDER BY seo_score DESC
        LIMIT ?
    """, (min_score, limit)).fetchall()
    return [dict(r) for r in rows]


# ─── BUILT PAGE TRACKING ─────────────────────────────────────────────────────

BUILT_DB = Path("built_pages.json")

def load_built() -> set:
    if BUILT_DB.exists():
        return set(json.loads(BUILT_DB.read_text()))
    return set()

def save_built(built: set):
    BUILT_DB.write_text(json.dumps(sorted(built), indent=2))


# ─── SLUG HELPER ─────────────────────────────────────────────────────────────

def make_slug(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:80]


# ─── GROQ CONTENT GENERATION (replaces Claude) ───────────────────────────────

def generate_article_content(client: Groq, signal: dict) -> dict | None:
    """Call Groq to generate full article body from a signal row."""
    primary_keyword    = signal.get("keyword_hint", signal["raw_title"])
    title              = signal.get("content_angle", signal["raw_title"])
    pain_summary       = signal.get("raw_title", "")

    h2_headers = [
        "What is actually happening",
        "Why this happens to expats in Germany",
        "Step-by-step: how to fix it",
        "What to do if you're stuck"
    ]
    secondary_keywords = [
        "expat Germany",
        "SCHUFA score",
        "German bank account",
        "blocked account Germany"
    ]

    prompt = """
You are a senior content writer for ExpatScore.de, an authoritative resource helping expats in Germany navigate SCHUFA, banking, taxes, and bureaucracy.

Write a complete, SEO-optimised article based on the following brief. Return ONLY a valid JSON object — no markdown, no fences.

BRIEF:
- Primary keyword : {primary_keyword}
- Article title   : {title}
- Pain point      : {pain_summary}
- H2 headers to cover: {h2_headers}
- Secondary keywords to weave in: {secondary_keywords}

Return this exact JSON shape (all fields required):

{{
  "intro_paragraph": "<2-3 sentence intro that hooks the reader by naming their exact pain, 80-120 words>",
  "sections": [
    {{
      "heading": "<H2 heading text>",
      "body": "<2-3 paragraph section body, 120-180 words, practical and specific>"
    }}
  ],
  "quick_tip": "<one concrete, actionable tip an expat can act on today, 1-2 sentences>",
  "faqs": [
    {{ "question": "<FAQ question>", "answer": "<concise 2-3 sentence answer>" }},
    {{ "question": "<FAQ question>", "answer": "<concise 2-3 sentence answer>" }},
    {{ "question": "<FAQ question>", "answer": "<concise 2-3 sentence answer>" }}
  ],
  "reading_time": <estimated reading time in minutes as integer>,
  "key_stats": [
    {{ "number": "<e.g. €7,200>", "label": "<short metric name, e.g. 'Average yearly cost'>" }},
    {{ "number": "<e.g. 2.5 years>", "label": "<e.g. 'Time to break even'>" }},
    {{ "number": "<e.g. 24 months>", "label": "<e.g. 'Required savings period'>" }},
    {{ "number": "<e.g. 98%>", "label": "<e.g. 'Success rate'>" }}
  ]
}}

Rules:
- Be specific to Germany (mention actual institutions, laws, timelines where relevant).
- Avoid generic advice. Every paragraph should give the reader something actionable.
- Naturally include the primary keyword in the intro and at least two H2 sections.
- Weave secondary keywords in naturally — never keyword-stuffed.
- Tone: clear, empathetic, authoritative. Not salesy.
- For the "body" field inside each section, you can use plain text with paragraphs separated by blank lines. It will be rendered as HTML automatically.
- The `key_stats` must contain exactly 4 entries with numbers and labels that are the most compelling, hard‑hitting metrics from the article.
""".format(
        primary_keyword=primary_keyword,
        title=title,
        pain_summary=pain_summary,
        h2_headers=json.dumps(h2_headers),
        secondary_keywords=json.dumps(secondary_keywords),
    )

    try:
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=MAX_TOKENS,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        return json.loads(raw)

    except json.JSONDecodeError as e:
        print(f"    WARN: JSON parse error — {e}")
        return None
    except Exception as e:
        print(f"    WARN: Groq API error — {e}")
        return None


# ─── PAGE RENDERER ───────────────────────────────────────────────────────────

def render_page(env: Environment, db: sqlite3.Connection, signal: dict, content: dict) -> tuple[str, str]:
    """Render the Jinja2 template and return (slug, html_string). Also saves intro paragraph to DB."""
    keyword = signal.get("keyword_hint", signal["raw_title"])
    slug    = make_slug(keyword)

    seo = {
        "title":               signal.get("content_angle", signal["raw_title"])[:60],
        "slug":                slug,
        "meta_description":    (signal.get("content_angle", "") + " — practical guide for expats in Germany.")[:155],
        "primary_keyword":     keyword,
        "secondary_keywords":  ["expat Germany", "SCHUFA", "German bank account", "blocked account"],
    }

    key_stats = content.get("key_stats", [])
    if len(key_stats) != 4:
        key_stats = [
            {"number": "€7,200", "label": "Average yearly cost"},
            {"number": "2.5 years", "label": "Time to break even"},
            {"number": "24 months", "label": "Required savings period"},
            {"number": "98%", "label": "Success rate"}
        ]

    template_vars = {
        "seo":              seo,
        "intro_paragraph":  content.get("intro_paragraph", ""),
        "sections":         content.get("sections", []),
        "quick_tip":        content.get("quick_tip", ""),
        "faqs":             content.get("faqs", []),
        "reading_time":     content.get("reading_time", 5),
        "partner_category": signal.get("partner_category", "general"),
        "generated_at":     datetime.utcnow().strftime("%Y-%m-%d"),
        "year":             date.today().year,
        "key_stats":        key_stats,
    }

    template = env.get_template("article.html")
    html = template.render(**template_vars)

    # Save intro paragraph to database for blog index
    intro = content.get("intro_paragraph", "")
    db.execute("UPDATE signals SET intro_paragraph = ? WHERE id = ?", (intro, signal["id"]))
    db.commit()

    return slug, html


# ─── MARKETING ASSETS GENERATION ───────────────────────────────────────────

def generate_marketing_assets(signal: dict, content: dict, slug: str):
    """Create a .txt file with Reddit-friendly marketing text for the article."""
    title = signal.get("content_angle", "Article")
    topic = signal.get("keyword_hint", title)
    quick_tip = content.get("quick_tip", "Check the full guide for details.")
    
    # Build the markdown table rows from key_stats
    key_stats = content.get("key_stats", [])
    table_rows = []
    for stat in key_stats:
        table_rows.append(f"| {stat['label']} | {stat['number']} |")
    
    table_header = "| **Aspect** | **Details** |\n|------------|-------------|\n"
    table_body = "\n".join(table_rows) if table_rows else "| Key takeaway | See full article |"
    
    # Generate the file content
    file_content = f"""### 🔍 Peer‑to‑Peer Hook

I went through the exact same struggle with **{topic}** in Germany, and I know how frustrating it can be. After months of research and personal experience, I've put together everything you need to know — no fluff, just practical steps.

---

### 📊 Key Insights

{table_header}{table_body}

---

### 💡 Quick Tip

{quick_tip}

---

### 🔎 How to Find This Article

Want the complete step‑by‑step guide? Just Google **"{title} ExpatScore.de"** — it'll be the first result. (Reddit doesn't love direct links, so that's the easiest way.)

---

### 🔗 Direct Link (for DMs)

https://expatscore.de/blog/{slug}.html
"""
    # Write the file
    output_path = OUTPUT_DIR / f"{slug}_marketing.txt"
    output_path.write_text(file_content, encoding="utf-8")
    return output_path


# ─── BLOG INDEX GENERATION ───────────────────────────────────────────────────

def update_blog_index(db: sqlite3.Connection):
    """Generate the main blog index page from all articles stored in the database."""
    print("\n[Blog] Generating blog index...")

    # Fetch all signals that have an intro paragraph (i.e., have been generated)
    rows = db.execute("""
        SELECT id, content_angle, keyword_hint, partner_category, intro_paragraph,
               seo_score, scored_at
        FROM signals
        WHERE intro_paragraph IS NOT NULL
          AND content_angle IS NOT NULL
          AND keyword_hint IS NOT NULL
        ORDER BY scored_at DESC
    """).fetchall()

    if not rows:
        print("[Blog] No articles found with intro paragraph. Skipping index generation.")
        return

    posts = []
    for row in rows:
        slug = make_slug(row["keyword_hint"])
        posts.append({
            "title": row["content_angle"],
            "slug": slug,
            "category": row["partner_category"] or "Guide",
            "summary": row["intro_paragraph"],
            "date": row["scored_at"][:10] if row["scored_at"] else "",
        })

    # Try to load blog template from current directory first, then from templates/
    template_path = None
    for path in [Path("."), TEMPLATE_DIR]:
        candidate = path / "blog_template.html"
        if candidate.exists():
            template_path = candidate
            break

    if template_path is None:
        print("[Blog] ERROR: blog_template.html not found in root or templates/.")
        return

    try:
        env = Environment(loader=FileSystemLoader(str(template_path.parent)), autoescape=True)
        template = env.get_template(template_path.name)
        html = template.render(posts=posts, year=date.today().year)
        output_file = OUTPUT_DIR / "blog.html"
        output_file.write_text(html, encoding="utf-8")
        print(f"[Blog] Written → {output_file}")
    except TemplateNotFound:
        print("[Blog] ERROR: Could not load blog_template.html")
    except Exception as e:
        print(f"[Blog] ERROR: {e}")


# ─── MAIN PIPELINE ───────────────────────────────────────────────────────────

def run(limit: int, min_score: int, dry_run: bool, force: bool):
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    db     = get_db()
    env    = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    built  = load_built()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    signals = fetch_top_signals(db, limit, min_score)
    if not signals:
        print(f"No signals found with seo_score >= {min_score}. Run signal_engine.py first.")
        return

    print(f"\nFound {len(signals)} signals (seo_score >= {min_score})")
    print(f"Output directory : {OUTPUT_DIR.resolve()}\n")

    generated = 0
    skipped   = 0

    for i, signal in enumerate(signals, 1):
        slug     = make_slug(signal.get("keyword_hint", signal["raw_title"]))
        out_path = OUTPUT_DIR / f"{slug}.html"
        preview  = (signal.get("keyword_hint") or signal["raw_title"])[:60]

        if slug in built and not force:
            print(f"  [{i}/{len(signals)}] SKIP (already built): {preview}")
            skipped += 1
            continue

        print(f"  [{i}/{len(signals)}] Generating: {preview}")
        print(f"           seo_score={signal['seo_score']}  slug={slug}")

        if dry_run:
            print(f"           [dry-run] would write → {out_path}")
            generated += 1
            continue

        content = generate_article_content(client, signal)
        if content is None:
            print(f"           WARN: Skipping — content generation failed.")
            continue

        slug_final, html = render_page(env, db, signal, content)
        final_path = OUTPUT_DIR / f"{slug_final}.html"
        final_path.write_text(html, encoding="utf-8")

        # Generate marketing assets
        marketing_path = generate_marketing_assets(signal, content, slug_final)
        print(f"           Written → {final_path}")
        print(f"           Marketing → {marketing_path}")

        built.add(slug_final)
        save_built(built)

        generated += 1
        time.sleep(REQUEST_DELAY)

    # Print summary
    print(f"\n{'─'*55}")
    print(f"  Pages generated : {generated}")
    print(f"  Pages skipped   : {skipped}")
    print(f"  Output folder   : {OUTPUT_DIR.resolve()}")
    if not dry_run:
        pages = list(OUTPUT_DIR.glob("*.html"))
        print(f"  Total in /docs  : {len(pages)} HTML files")
        print(f"\n  Deploy hint: if your site runs on GitHub Pages,")
        print(f"  commit the /docs folder — pages go live automatically.")
    print(f"{'─'*55}\n")

    # Generate blog index after all articles are done
    if not dry_run:
        update_blog_index(db)


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ExpatScore Programmatic SEO Page Generator")
    parser.add_argument("--limit",     type=int, default=10,  help="Max pages to generate (default 10)")
    parser.add_argument("--min-score", type=int, default=60,  help="Minimum seo_score to include (default 60)")
    parser.add_argument("--dry-run",   action="store_true",   help="Preview without writing files")
    parser.add_argument("--force",     action="store_true",   help="Regenerate already-built pages")
    args = parser.parse_args()

    run(
        limit     = args.limit,
        min_score = args.min_score,
        dry_run   = args.dry_run,
        force     = args.force,
    )