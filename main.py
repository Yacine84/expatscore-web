# =============================================================================
# main.py — ExpatScore.de Sniper Coordinator + Page Generator
# Version: 2.0 | Phase 1 — SEO Foundation Edition
#
# Changes from 1.2:
#   - Added full blog page generator (generate_blog_pages)
#   - Passes all JSON-LD / SEO fields to blog_template.html:
#       post.date_iso, post.date_modified_iso, post.read_minutes,
#       post.word_count, post.faqs, post.affiliate_card, post.related_slugs,
#       post.has_affiliate_links, post.keywords, post.meta_description,
#       post.lang, post.lang_de_slug
#   - Built-in Jinja2 rendering (no external dependency beyond jinja2)
#   - Sitemap auto-regenerated after every build run
#   - Keeps Sniper Coordinator workers unchanged (reddit + youtube)
# =============================================================================

import threading
import logging
import time
import sys
import os
import json
import re
import math
from datetime import datetime, date
from pathlib import Path

# =============================================================================
# LOAD .env FIRST — Before any worker module imports os.getenv()
# =============================================================================

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[Coordinator] ✅ .env loaded")
except ImportError:
    print("[Coordinator] ⚠  python-dotenv not installed — using system env vars")

# =============================================================================
# SHARED LOGGING
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("expatscorebot.log", encoding="utf-8"),
    ],
)

log = logging.getLogger("Coordinator")

# =============================================================================
# PATHS — adjust if your repo layout differs
# =============================================================================

BASE_DIR      = Path(__file__).parent.resolve()
DOCS_DIR      = BASE_DIR / "docs"
BLOG_DIR      = DOCS_DIR / "blog"
TEMPLATE_FILE = DOCS_DIR / "blog_template.html"   # article template
DATA_DIR      = BASE_DIR / "data"                  # JSON posts live here
BUILT_FILE    = BASE_DIR / "built_pages.json"      # tracks already-built slugs

# =============================================================================
# PAGE GENERATOR — renders JSON post data into production HTML
# =============================================================================

def _estimate_read_minutes(html_or_text: str) -> int:
    """Returns estimated reading time in minutes (200 wpm average)."""
    text = re.sub(r'<[^>]+>', ' ', html_or_text)   # strip HTML tags
    words = len(text.split())
    return max(1, math.ceil(words / 200))


def _estimate_word_count(html_or_text: str) -> int:
    text = re.sub(r'<[^>]+>', ' ', html_or_text)
    return len(text.split())


def _to_iso_date(date_str: str) -> str:
    """
    Converts common date formats to ISO-8601 (YYYY-MM-DD).
    Passes through strings already in ISO format.
    Falls back to today's date on parse failure.
    """
    if not date_str:
        return date.today().isoformat()
    # Already ISO?
    if re.match(r'^\d{4}-\d{2}-\d{2}', date_str):
        return date_str[:10]
    # Try common formats
    for fmt in ('%B %d, %Y', '%d %B %Y', '%d.%m.%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue
    log.warning(f"  ⚠  Could not parse date '{date_str}' — using today")
    return date.today().isoformat()


def _enrich_post(post: dict) -> dict:
    """
    Takes raw JSON post data and adds all derived SEO fields that
    blog_template.html expects. Non-destructive: never overwrites
    fields the JSON already provides explicitly.
    """
    post = dict(post)   # shallow copy — don't mutate original

    # ── Dates ────────────────────────────────────────────────────────────────
    post.setdefault('date', date.today().strftime('%B %d, %Y'))
    post['date_iso']          = _to_iso_date(post.get('date_iso', post['date']))
    post['date_modified_iso'] = _to_iso_date(
        post.get('date_modified_iso', post.get('date_modified', post['date_iso']))
    )

    # ── Reading time + word count ─────────────────────────────────────────────
    content = post.get('content_html', post.get('content', ''))
    post.setdefault('read_minutes', _estimate_read_minutes(content))
    post.setdefault('word_count',   _estimate_word_count(content))

    # ── content_html alias ────────────────────────────────────────────────────
    if 'content_html' not in post and 'content' in post:
        post['content_html'] = post['content']

    # ── Meta description fallback ─────────────────────────────────────────────
    if 'meta_description' not in post:
        summary = post.get('summary', '')
        post['meta_description'] = summary[:155] + ('…' if len(summary) > 155 else '')

    # ── Keywords fallback ────────────────────────────────────────────────────
    post.setdefault('keywords', 'expat Germany, SCHUFA, banking, credit score, expat finance')

    # ── Language ─────────────────────────────────────────────────────────────
    post.setdefault('lang', 'en')

    # ── Affiliate flag: True if post has any affiliate_card or link in content ─
    has_affiliate = bool(post.get('affiliate_card')) or \
                    bool(post.get('has_affiliate_links')) or \
                    'affiliate' in content.lower() or \
                    'sponsored' in content.lower()
    post.setdefault('has_affiliate_links', has_affiliate)

    # ── FAQs: ensure list, skip if empty ─────────────────────────────────────
    faqs = post.get('faqs', [])
    if isinstance(faqs, list) and all(
        isinstance(f, dict) and 'question' in f and 'answer' in f
        for f in faqs
    ):
        post['faqs'] = faqs
    else:
        post['faqs'] = []

    # ── Affiliate card: validate required keys ────────────────────────────────
    card = post.get('affiliate_card')
    if card and isinstance(card, dict):
        required_keys = {'name', 'category', 'url', 'description'}
        if not required_keys.issubset(card.keys()):
            log.warning(f"  ⚠  affiliate_card for '{post.get('slug')}' missing keys "
                        f"{required_keys - card.keys()} — card suppressed")
            post['affiliate_card'] = None
    else:
        post['affiliate_card'] = None

    # ── Related slugs: validate structure ─────────────────────────────────────
    related = post.get('related_slugs', [])
    if isinstance(related, list) and all(
        isinstance(r, dict) and 'slug' in r and 'title' in r
        for r in related
    ):
        post['related_slugs'] = related
    else:
        post['related_slugs'] = []

    return post


def generate_blog_pages(data_glob: str = "*.json") -> list[str]:
    """
    Scans DATA_DIR for JSON post files, enriches them, renders
    blog_template.html via Jinja2, and writes to BLOG_DIR/<slug>.html.

    Each JSON file must have at minimum:
        {
          "slug":    "my-article-slug",
          "title":   "Article Title",
          "summary": "One-sentence summary.",
          "content_html": "<p>...</p>"   (or "content": "...")
        }

    Optional but recommended fields:
        "date":               "April 14, 2026"
        "date_iso":           "2026-04-14"
        "date_modified_iso":  "2026-04-14"
        "category":           "Banking"
        "keywords":           "schufa, bank account expat, ..."
        "meta_description":   "Concise 155-char SEO description."
        "read_minutes":       6
        "word_count":         1400
        "lang":               "en"
        "lang_de_slug":       null  (or "de-slug" when German version exists)
        "has_affiliate_links": true
        "faqs": [
          { "question": "...", "answer": "..." }
        ]
        "affiliate_card": {
          "name":        "N26 Standard",
          "category":    "Digital Bank · Expat-Friendly",
          "logo_text":   "N26",
          "url":         "https://your-affiliate-link.com",
          "description": "...",
          "cta_text":    "Open Account Free →",
          "rating":      4.1,
          "features": [
            { "label": "No Schufa Check", "type": "default" },
            { "label": "EU Passport Only", "type": "gold" }
          ]
        }
        "related_slugs": [
          { "slug": "schufa-guide", "title": "Complete SCHUFA Guide" }
        ]

    Returns a list of successfully built slugs.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except ImportError:
        log.critical("❌ jinja2 not installed. Run: pip install jinja2")
        return []

    if not TEMPLATE_FILE.exists():
        log.critical(f"❌ Template not found: {TEMPLATE_FILE}")
        return []

    BLOG_DIR.mkdir(parents=True, exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(DOCS_DIR)),
        autoescape=select_autoescape(['html']),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    template = env.get_template("blog_template.html")

    # Load previously-built slugs
    built: list[str] = []
    if BUILT_FILE.exists():
        try:
            built = json.loads(BUILT_FILE.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            built = []

    newly_built: list[str] = []
    data_files  = sorted(DATA_DIR.glob(data_glob)) if DATA_DIR.exists() else []

    if not data_files:
        log.warning(f"  ⚠  No JSON data files found in {DATA_DIR}")
        return []

    log.info(f"  📄 Found {len(data_files)} post file(s) in {DATA_DIR}")

    for data_file in data_files:
        # --- FIX: Skip dot-files (e.g., .dedup_registry.json, .session_state.json)
        if data_file.name.startswith('.'):
            log.info(f"  ⏭  Skipping dot-file: {data_file.name}")
            continue

        try:
            raw_post = json.loads(data_file.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError) as e:
            log.error(f"  ✖ Failed to read {data_file.name}: {e}")
            continue

        # --- FIX: Handle JSON that is a list instead of a dict
        if isinstance(raw_post, list):
            if len(raw_post) == 0:
                log.warning(f"  ⚠  {data_file.name} contains an empty list — skipping")
                continue
            # Take the first element of the list (assuming it's the actual post)
            raw_post = raw_post[0]
            log.info(f"  🔄 {data_file.name} was a list — using first element as post")

        # Ensure we now have a dictionary
        if not isinstance(raw_post, dict):
            log.warning(f"  ⚠  {data_file.name} does not contain a valid post object (type: {type(raw_post).__name__}) — skipping")
            continue

        slug = raw_post.get('slug') or data_file.stem
        if not slug:
            log.warning(f"  ⚠  No slug in {data_file.name} — skipping")
            continue

        out_path = BLOG_DIR / f"{slug}.html"

        # Skip already-built pages unless data file is newer
        if slug in built and out_path.exists():
            data_mtime = data_file.stat().st_mtime
            out_mtime  = out_path.stat().st_mtime
            if data_mtime <= out_mtime:
                log.info(f"  ⏭  {slug} — up to date, skipping")
                continue

        post = _enrich_post(raw_post)
        post['slug'] = slug

        try:
            html = template.render(
                post=post,
                year=datetime.now().year,
            )
            out_path.write_text(html, encoding='utf-8')
            log.info(f"  ✅ Built: blog/{slug}.html "
                     f"({post['word_count']} words · {post['read_minutes']} min read"
                     f"{'· FAQs: ' + str(len(post['faqs'])) if post['faqs'] else ''}"
                     f"{'· affiliate ✓' if post['affiliate_card'] else ''})")
            newly_built.append(slug)
        except Exception as e:
            log.error(f"  ✖ Render failed for {slug}: {e}", exc_info=True)

    # Update built_pages.json
    all_built = sorted(set(built + newly_built))
    BUILT_FILE.write_text(
        json.dumps(all_built, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )

    log.info(f"  📊 Generator summary: {len(newly_built)} built, "
             f"{len(built)} already current, "
             f"{len(all_built)} total tracked")

    return newly_built


def regenerate_sitemap(base_url: str = "https://expatscore.de") -> None:
    """
    Rewrites docs/sitemap.xml scanning all HTML in docs/.
    Respects existing priority values for known top-level pages.
    """
    sitemap_path = DOCS_DIR / "sitemap.xml"
    today = date.today().isoformat()

    # Known page priorities
    PRIORITIES = {
        '':                  ('1.0', 'weekly'),
        'schufa-simulator':  ('0.9', 'weekly'),
        'schufa-guide':      ('0.85', 'monthly'),
        'banking':           ('0.8', 'weekly'),
        'insurance':         ('0.8', 'weekly'),
        'blue-card-tool':    ('0.9', 'weekly'),
        'blog/':             ('0.7', 'weekly'),
    }

    urls = []
    for html_file in sorted(DOCS_DIR.rglob('*.html')):
        rel = html_file.relative_to(DOCS_DIR)
        parts = list(rel.parts)
        # Build URL path
        if parts[-1] == 'index.html':
            parts[-1] = ''
        else:
            parts[-1] = parts[-1].replace('.html', '')
        url_path = '/'.join(parts).strip('/')

        # Skip legal/utility pages from high priority
        skip_patterns = ['impressum', 'datenschutz', 'affiliate-hinweis', '404']
        if any(p in url_path for p in skip_patterns):
            priority, changefreq = '0.3', 'yearly'
        elif url_path.startswith('blog/') and url_path != 'blog/':
            priority, changefreq = '0.6', 'monthly'
        else:
            priority, changefreq = PRIORITIES.get(url_path, ('0.6', 'monthly'))

        full_url = f"{base_url}/{url_path}" if url_path else base_url + '/'
        urls.append((full_url, today, changefreq, priority))

    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for full_url, lastmod, changefreq, priority in urls:
        lines += [
            '  <url>',
            f'    <loc>{full_url}</loc>',
            f'    <lastmod>{lastmod}</lastmod>',
            f'    <changefreq>{changefreq}</changefreq>',
            f'    <priority>{priority}</priority>',
            '  </url>',
        ]
    lines.append('</urlset>')

    sitemap_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    log.info(f"  🗺  Sitemap regenerated: {len(urls)} URLs → {sitemap_path}")


# =============================================================================
# IMPORT WORKERS — After .env is loaded and logging is configured
# =============================================================================

try:
    import reddit_worker
    import youtube_worker
    WORKERS_AVAILABLE = True
except ImportError as e:
    log.warning(f"⚠  Worker import failed ({e}) — sniper mode unavailable in this env")
    WORKERS_AVAILABLE = False

# =============================================================================
# THREAD FACTORY
# =============================================================================

def make_thread(target_fn, name: str) -> threading.Thread:
    return threading.Thread(target=target_fn, name=name, daemon=True)

# =============================================================================
# WORKER WRAPPERS
# =============================================================================

def run_reddit():
    log.info("🟠 [Reddit Worker] Thread started.")
    try:
        reddit_worker.main()
    except Exception as e:
        log.critical(f"💥 [Reddit Worker] Fatal crash: {e}", exc_info=True)

def run_youtube():
    log.info("🔴 [YouTube Worker] Thread started.")
    try:
        youtube_worker.main()
    except Exception as e:
        log.critical(f"💥 [YouTube Worker] Fatal crash: {e}", exc_info=True)

# =============================================================================
# COORDINATOR MAIN
# =============================================================================

def main():
    log.info("=" * 65)
    log.info("🚀 ExpatScore Coordinator v2.0 — SEO Foundation Edition")
    log.info("   Workers  : RedditWorker + YouTubeWorker")
    log.info("   Generator: Jinja2 blog page builder with schema injection")
    log.info("   Scoring  : Groq llama3 (fallback: keyword heuristic)")
    log.info("   Watchdog : Auto-restarts dead threads every 5 min")
    log.info("=" * 65)

    # ── Run page generator first (fast, synchronous) ──────────────────────
    log.info("\n📐 Running page generator...")
    newly_built = generate_blog_pages()
    if newly_built:
        log.info(f"  🗺  Regenerating sitemap after {len(newly_built)} new page(s)...")
        regenerate_sitemap()
    else:
        log.info("  ✅ All pages up to date — no sitemap regeneration needed")

    # ── Environment validation for snipers ───────────────────────────────
    missing_critical = []
    missing_warned   = []

    if not os.getenv("N8N_WEBHOOK_URL"):
        missing_critical.append("N8N_WEBHOOK_URL")
    if not os.getenv("YOUTUBE_API_KEY"):
        missing_critical.append("YOUTUBE_API_KEY")
    if not os.getenv("GROQ_API_KEY"):
        missing_warned.append("GROQ_API_KEY")

    # If only running generator (e.g. CI/CD deploy), allow clean exit
    if os.getenv("GENERATOR_ONLY"):
        log.info("✅ GENERATOR_ONLY mode — exiting after page generation.")
        sys.exit(0)

    if not WORKERS_AVAILABLE:
        log.warning("⚠  Worker modules not available — sniper mode disabled.")
        log.info("✅ Page generation complete. Exiting.")
        sys.exit(0)

    if missing_critical:
        log.critical(f"🚫 Missing required .env variables: {missing_critical}")
        log.critical("   Add them to your .env file and restart.")
        sys.exit(1)

    if missing_warned:
        log.warning(f"⚠  GROQ_API_KEY not set — fallback keyword scoring active.")

    log.info("✅ Environment check passed")

    # ── Start Reddit thread ───────────────────────────────────────────────
    reddit_thread = make_thread(run_reddit, "RedditWorker")
    reddit_thread.start()
    log.info("🟠 Reddit worker launched")

    time.sleep(15)

    youtube_thread = make_thread(run_youtube, "YouTubeWorker")
    youtube_thread.start()
    log.info("🔴 YouTube worker launched")

    log.info("✅ Both workers running. Press Ctrl+C to stop all.")

    # ── Watchdog: auto-restart dead threads ───────────────────────────────
    try:
        while True:
            time.sleep(300)
            if not reddit_thread.is_alive():
                log.critical("🟠 [Watchdog] Reddit thread dead — RESTARTING")
                reddit_thread = make_thread(run_reddit, "RedditWorker")
                reddit_thread.start()
            if not youtube_thread.is_alive():
                log.critical("🔴 [Watchdog] YouTube thread dead — RESTARTING")
                youtube_thread = make_thread(run_youtube, "YouTubeWorker")
                youtube_thread.start()
    except KeyboardInterrupt:
        log.info("🔴 Ctrl+C received — shutting down. Goodbye.")
        sys.exit(0)

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()